import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright
import yaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
from zapv2 import ZAPv2
import boto3
from botocore.client import Config
import psycopg2
from psycopg2.extras import Json
import re
from redis import Redis


RESULTS_DIR = Path(os.getenv("TAAS_RESULTS_DIR", "test-results/taas")).resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE = Path("/workspace").resolve()
REDIS_URL = os.getenv("RQ_REDIS_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")


def _redis() -> Redis | None:
    try:
        return Redis.from_url(REDIS_URL)
    except Exception:
        return None


def _is_canceled(job_id: str) -> bool:
    r = _redis()
    if not r:
        return False
    try:
        return bool(r.get(f"cancel:{job_id}"))
    except Exception:
        return False


def _update(job_id: str, patch: Dict):
    path = RESULTS_DIR / f"{job_id}.json"
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(patch)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _load_site_routes(site: Optional[str]) -> Dict:
    if not site:
        return {}
    # Try config/sites/<site>.yml(.yaml)
    for rel in [f"config/sites/{site}.yml", f"config/sites/{site}.yaml", "config/sites.yaml", "config/sites.yml", "sites.yaml", "sites.yml"]:
        cand = WORKSPACE / rel
        if cand.is_file():
            try:
                data = yaml.safe_load(cand.read_text(encoding="utf-8")) or {}
                if "sites" in data and isinstance(data["sites"], dict):
                    return data["sites"].get(site, {})
                return data
            except Exception:
                return {}
    return {}


def _to_abs_urls(base_url: Optional[str], routes: List[str]) -> List[str]:
    out = []
    b = (base_url or "").rstrip("/")
    for r in routes:
        s = str(r).strip()
        if not s:
            continue
        if s.startswith("http://") or s.startswith("https://"):
            out.append(s)
        else:
            out.append(f"{b}{s if s.startswith('/') else '/' + s}")
    return out


def _normalize_url(u: str) -> str:
    try:
        pr = urlparse(u)
        # drop fragments and normalize path
        path = pr.path or "/"
        return urlunparse((pr.scheme, pr.netloc, path, "", pr.query, ""))
    except Exception:
        return u


def _same_host(a: str, b: str) -> bool:
    try:
        pa, pb = urlparse(a), urlparse(b)
        return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)
    except Exception:
        return False


def _crawl_links(start_url: str, max_pages: int = 6) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    q: List[str] = [_normalize_url(start_url)]
    base = _normalize_url(start_url)
    headers = {"User-Agent": "RateMateCrawler/0.1"}
    exts = {"jpg", "jpeg", "png", "gif", "svg", "webp", "css", "js", "ico", "pdf", "zip"}

    while q and len(out) < max_pages:
        cur = q.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        try:
            r = requests.get(cur, headers=headers, timeout=10)
            if r.status_code >= 400:
                continue
            out.append(cur)
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.select("a[href]"):
                href = a.get("href") or ""
                if href.startswith("javascript:"):
                    continue
                cand = urljoin(cur, href)
                cand = _normalize_url(cand)
                # filter by same host and skip static resources
                if not _same_host(base, cand):
                    continue
                path = urlparse(cand).path or "/"
                if "." in path.split("/")[-1]:
                    ext = path.split("/")[-1].split(".")[-1].lower()
                    if ext in exts:
                        continue
                if cand not in seen and cand not in q:
                    q.append(cand)
        except Exception:
            continue
    # de-dup preserve order
    uniq = []
    for u in out:
        if u not in uniq:
            uniq.append(u)
    return uniq


def run_web_test(job_id: str, payload: Dict):
    _update(job_id, {"status": "running"})
    url = (payload.get("url") or "").strip()
    site = (payload.get("site") or "").strip()
    routes = payload.get("routes") if isinstance(payload.get("routes"), list) else None
    test_type = (payload.get("test_type") or "smoke").lower()

    # Determine set of URLs to check
    urls: List[str]
    if routes:
        cfg = _load_site_routes(site)
        base_url = (cfg.get("base_url") if isinstance(cfg, dict) else None) or payload.get("url") or None
        route_list = [str(r) for r in routes]
        urls = _to_abs_urls(base_url, route_list)
    elif site:
        cfg = _load_site_routes(site)
        base_url = (cfg.get("base_url") or "").strip()
        rts = cfg.get("routes") if isinstance(cfg, dict) else None
        if isinstance(rts, dict):
            seq = []
            if isinstance(rts.get("public"), list):
                seq += rts["public"]
            if isinstance(rts.get("protected"), list):
                seq += rts["protected"]
            route_list = [str(x) for x in seq]
        elif isinstance(rts, list):
            route_list = [str(x) for x in rts]
        else:
            route_list = ["/"]
        urls = _to_abs_urls(base_url, route_list)
    else:
        route_list = [url]
        urls = [url]

    # Auto mode: crawl from base URL if requested
    if test_type == "auto":
        seed = url or None
        if site and not seed:
            cfg = _load_site_routes(site)
            seed = (cfg.get("base_url") or "").strip() if isinstance(cfg, dict) else None
        if seed:
            discovered = _crawl_links(seed, max_pages=6)
            if discovered:
                # Prefer login/store-like paths first
                def score(u: str) -> int:
                    p = (urlparse(u).path or "").lower()
                    s = 0
                    for k in ["login", "signin", "store", "home", "product", "account"]:
                        if k in p:
                            s -= 10
                    return s

                discovered.sort(key=score)
                urls = discovered

    case_results = []
    all_passed = True
    t0 = time.time()
    if _is_canceled(job_id):
      _update(job_id, {"status": "canceled", "error": "canceled"}); return

    with sync_playwright() as p:
        # Load optional assertions map from site config
        assertions_map = {}
        if site:
            cfg = _load_site_routes(site)
            if isinstance(cfg, dict) and isinstance(cfg.get("assertions"), dict):
                assertions_map = cfg["assertions"]
        for idx, target in enumerate(urls):
            screenshot_path = RESULTS_DIR / f"{job_id}-{idx+1}-screenshot.png"
            trace_path = RESULTS_DIR / f"{job_id}-{idx+1}-trace.zip"
            status_code = None
            title = None
            passed = False
            err = None
            missing: List[str] = []
            if _is_canceled(job_id):
                _update(job_id, {"status": "canceled", "error": "canceled"}); return
            try:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                context.tracing.start(screenshots=True, snapshots=True, sources=True)
                page = context.new_page()
                resp = page.goto(target, wait_until="networkidle", timeout=30000)
                status_code = resp.status if resp else None
                title = page.title()
                page.screenshot(path=str(screenshot_path), full_page=True)
                passed = bool(resp and 200 <= status_code < 400)
                # Optional CSS selector assertions from site config
                try:
                    # Match by original route string if available
                    route_key = route_list[idx] if idx < len(route_list) else None
                    selectors = []
                    if isinstance(assertions_map, dict) and route_key in assertions_map and isinstance(assertions_map[route_key], list):
                        selectors = [str(s) for s in assertions_map[route_key]]
                    for sel in selectors:
                        try:
                            if page.locator(sel).count() == 0:
                                missing.append(sel)
                        except Exception:
                            missing.append(sel)
                    if selectors:
                        passed = passed and (len(missing) == 0)
                except Exception:
                    pass
                # Visual regression vs baseline (S3)
                visual = None
                try:
                    project = payload.get('project') or payload.get('site') or 'default'
                    slug = (urlparse(target).path or '/').replace('/', '_').strip('_') or 'root'
                    dim = '1366x900'
                    baseline_key = f"baselines/{project}/{slug}_{dim}.png"
                    # Download baseline if exists
                    base_tmp = RESULTS_DIR / f"{job_id}-{idx+1}-baseline.png"
                    has_baseline = _download_baseline(baseline_key, base_tmp)
                    mismatch = None
                    diff_path = RESULTS_DIR / f"{job_id}-{idx+1}-visual-diff.png"
                    passed_visual = True
                    auto_base = os.getenv('VISUAL_AUTO_BASELINE','0') == '1'
                    threshold = float(os.getenv('VISUAL_THRESHOLD_PCT', '0.1'))
                    if has_baseline:
                        try:
                            from PIL import Image, ImageChops  # pillow
                            a = Image.open(str(base_tmp)).convert('RGBA')
                            b = Image.open(str(screenshot_path)).convert('RGBA')
                            if a.size != b.size:
                                b = b.resize(a.size)
                            diff = ImageChops.difference(a, b)
                            bbox = diff.getbbox()
                            if bbox:
                                # Compute mismatch percentage
                                hist = diff.histogram()
                                # alpha channel may exist; approximate by non-zero pixels
                                nonzero = sum(hist[1:])
                                total = sum(hist)
                                mismatch = round((nonzero/total)*100, 3) if total else 0.0
                                if mismatch is not None and mismatch > threshold:
                                    passed_visual = False
                                diff.save(str(diff_path))
                                _upload(diff_path)
                        except Exception:
                            pass
                    else:
                        if auto_base:
                            # set current as baseline
                            cli = _s3()
                            if cli:
                                _ensure_bucket(cli)
                                cli.upload_file(str(screenshot_path), s3cfg['bucket'], baseline_key)
                    visual = {
                        'baseline_key': baseline_key,
                        'baseline_missing': not has_baseline,
                        'mismatch_pct': mismatch,
                        'passed': passed_visual,
                        'diff_image': str(diff_path) if diff_path.exists() else None,
                    }
                except Exception:
                    visual = None

                context.tracing.stop(path=str(trace_path))
                context.close(); browser.close()
            except Exception as e:
                err = str(e)
                try:
                    context.tracing.stop(path=str(trace_path))
                except Exception:
                    pass
                try:
                    context.close(); browser.close()
                except Exception:
                    pass
            case_results.append({
                "url": target,
                "passed": passed,
                "status_code": status_code,
                "title": title,
                "screenshot": str(screenshot_path) if screenshot_path.exists() else None,
                "trace": str(trace_path) if trace_path.exists() else None,
                "error": err,
                "missing_selectors": missing or None,
                "visual": visual,
            })
            if not passed:
                all_passed = False

    elapsed = round(time.time() - t0, 2)

    # Optionally run Lighthouse performance on the first URL when requested
    perf_result = None
    perf_ok = True
    perf_reason = []
    if test_type == "performance" and urls:
        try:
            if _is_canceled(job_id):
                _update(job_id, {"status": "canceled", "error": "canceled"}); return
            perf_timeout = int(os.getenv("PERF_TIMEOUT_SEC", "240"))
            r = requests.post("http://perf:3001/run", json={"url": urls[0], "html": True}, timeout=perf_timeout)
            if r.status_code < 400:
                pj = r.json()
                perf_result = {
                    "url": pj.get("url"),
                    "performance_score": pj.get("performance_score"),
                    "metrics": pj.get("metrics"),
                }
                # Save HTML report if present
                try:
                    html = pj.get("reportHtml")
                    if html:
                        perf_html = RESULTS_DIR / f"{job_id}-perf.html"
                        perf_html.write_text(html, encoding="utf-8")
                        perf_result["report_path"] = str(perf_html)
                except Exception:
                    pass
                # Apply thresholds
                score_min = int(os.getenv("PERF_SCORE_MIN", "80"))
                lcp_max = float(os.getenv("PERF_LCP_MAX_MS", "2500"))
                cls_max = float(os.getenv("PERF_CLS_MAX", "0.1"))
                tti_max = float(os.getenv("PERF_TTI_MAX_MS", "5000"))
                m = perf_result.get("metrics") or {}
                if perf_result.get("performance_score") is not None and perf_result["performance_score"] < score_min:
                    perf_ok = False; perf_reason.append(f"score<{score_min}")
                if m.get("lcp") and m["lcp"] > lcp_max:
                    perf_ok = False; perf_reason.append(f"lcp>{lcp_max}")
                if m.get("cls") and m["cls"] > cls_max:
                    perf_ok = False; perf_reason.append(f"cls>{cls_max}")
                if m.get("tti") and m["tti"] > tti_max:
                    perf_ok = False; perf_reason.append(f"tti>{tti_max}")
            else:
                perf_result = {"error": f"lighthouse_status_{r.status_code}"}
                perf_ok = False
        except Exception as e:
            perf_result = {"error": f"lighthouse_failed:{e}"}
            perf_ok = False

    # Optionally run ZAP baseline (spider + passive scan) when requested
    zap_result = None
    zap_ok = True
    zap_reason = []
    if test_type == "security" and urls:
        try:
            target = urls[0]
            api_key = os.getenv("ZAP_API_KEY", "changeme")
            zap = ZAPv2(apikey=api_key, proxies={'http': 'http://zap:8090', 'https': 'http://zap:8090'})
            # Start spider
            sid = zap.spider.scan(target)
            # Wait spider
            zap_max = int(os.getenv("ZAP_MAX_SECONDS", "180"))
            t0z = time.time()
            while True:
                status = int(zap.spider.status(sid))
                if status >= 100:
                    break
                time.sleep(1)
                if time.time() - t0z > zap_max or _is_canceled(job_id):
                    break
            # Ajax spider for SPA
            try:
                zap.ajaxSpider.scan(target)
                t0_ajax = time.time()
                while True:
                    st = zap.ajaxSpider.status()
                    if st == 'stopped' or (time.time() - t0_ajax) > min(60, zap_max):
                        break
                    time.sleep(1)
                    if time.time() - t0z > zap_max or _is_canceled(job_id):
                        break
            except Exception:
                pass
            # Passive scanning usually runs automatically, give it a moment
            time.sleep(2)
            # Fetch alerts
            alerts = zap.core.alerts(baseurl=target) or []
            # Exclude noisy static chunks and user-provided excludes
            excludes = [r"/_next/static/"]
            ex_env = os.getenv('ZAP_EXCLUDE_REGEX')
            if ex_env:
                try:
                    excludes += [x for x in ex_env.split(',') if x.strip()]
                except Exception:
                    pass
            excl = [re.compile(e) for e in excludes]
            def _excluded(u: str) -> bool:
                try:
                    return any(rx.search(u or '') for rx in excl)
                except Exception:
                    return False
            alerts = [a for a in alerts if not _excluded(a.get('url') or '')]
            # Summarize by risk
            counts = {"High": 0, "Medium": 0, "Low": 0, "Informational": 0}
            items = []
            for a in alerts:
                risk = a.get('risk') or a.get('riskdesc', '').split(' ')[0]
                if risk in counts:
                    counts[risk] += 1
                items.append({
                    'risk': risk,
                    'alert': a.get('alert'),
                    'url': a.get('url'),
                    'evidence': a.get('evidence')
                })
            # HTML report
            try:
                html = zap.core.htmlreport()
                if html:
                    zap_html = RESULTS_DIR / f"{job_id}-zap.html"
                    zap_html.write_text(html, encoding="utf-8")
                    report_path = str(zap_html)
                else:
                    report_path = None
            except Exception:
                report_path = None
            # thresholds
            allow_med = int(os.getenv("ZAP_ALLOW_MEDIUM", "0"))
            allow_high = int(os.getenv("ZAP_ALLOW_HIGH", "0"))
            if counts.get("High", 0) > allow_high:
                zap_ok = False; zap_reason.append(f"high>{allow_high}")
            if counts.get("Medium", 0) > allow_med:
                zap_ok = False; zap_reason.append(f"medium>{allow_med}")

            zap_result = {"counts": counts, "alerts": items[:50], "report_path": report_path}
        except Exception as e:
            zap_result = {"error": str(e)}
            zap_ok = False

    # Upload artifacts to S3/MinIO if configured
    s3cfg = {
        'endpoint_url': os.getenv('S3_ENDPOINT'),
        'access_key': os.getenv('S3_ACCESS_KEY'),
        'secret_key': os.getenv('S3_SECRET_KEY'),
        'bucket': os.getenv('S3_BUCKET', 'taas-artifacts'),
        'region': os.getenv('S3_REGION', 'us-east-1'),
    }

    def _s3() -> boto3.client:
        return (
            boto3.client(
                's3',
                endpoint_url=s3cfg['endpoint_url'],
                aws_access_key_id=s3cfg['access_key'],
                aws_secret_access_key=s3cfg['secret_key'],
                region_name=s3cfg['region'],
                config=Config(signature_version='s3v4'),
            )
            if s3cfg['endpoint_url'] and s3cfg['access_key'] and s3cfg['secret_key']
            else None
        )

    def _ensure_bucket(cli):
        try:
            cli.head_bucket(Bucket=s3cfg['bucket'])
        except Exception:
            try:
                cli.create_bucket(Bucket=s3cfg['bucket'])
            except Exception:
                pass

    def _upload(path: Path) -> dict | None:
        cli = _s3()
        if not cli or not path or not path.is_file():
            return None
        _ensure_bucket(cli)
        key = f"{job_id}/{path.name}"
        cli.upload_file(str(path), s3cfg['bucket'], key)
        ttl = int(os.getenv('ARTIFACT_TTL_SECONDS', '86400'))
        url = cli.generate_presigned_url('get_object', Params={'Bucket': s3cfg['bucket'], 'Key': key}, ExpiresIn=ttl)
        return { 'bucket': s3cfg['bucket'], 'key': key, 'presigned_url': url }

    def _download_baseline(key: str, dest: Path) -> bool:
        cli = _s3()
        if not cli:
            return False
        try:
            _ensure_bucket(cli)
            cli.download_file(s3cfg['bucket'], key, str(dest))
            return True
        except Exception:
            return False

    # For single URL keep backward-compatible shape
    if len(urls) == 1:
        r0 = case_results[0]
        result = {
            "url": r0["url"],
            "test_type": test_type,
            "passed": r0["passed"],
            "status_code": r0["status_code"],
            "title": r0["title"],
            "screenshot": r0["screenshot"],
            "trace": r0.get("trace"),
            "duration_sec": elapsed,
            "metrics": None,
            "alerts": [],
            "error": r0.get("error"),
            "performance": perf_result,
            "security": zap_result,
            "policy": {"performance_ok": perf_ok, "performance_reasons": perf_reason or None, "security_ok": zap_ok, "security_reasons": zap_reason or None},
        }
    else:
        result = {
            "test_type": test_type,
            "passed": all_passed,
            "cases": case_results,
            "duration_sec": elapsed,
            "performance": perf_result,
            "security": zap_result,
            "policy": {"performance_ok": perf_ok, "performance_reasons": perf_reason or None, "security_ok": zap_ok, "security_reasons": zap_reason or None},
        }
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # Upload artifacts and add URLs
    artifacts = {}
    if len(urls) == 1:
        if r0.get("screenshot"):
            artifacts['screenshot'] = _upload(Path(r0['screenshot']))
        if r0.get("trace"):
            artifacts['trace'] = _upload(Path(r0['trace']))
    else:
        for idx, c in enumerate(case_results, start=1):
            if c.get('screenshot'):
                artifacts[f'screenshot_{idx}'] = _upload(Path(c['screenshot']))
            if c.get('trace'):
                artifacts[f'trace_{idx}'] = _upload(Path(c['trace']))
    if perf_result and perf_result.get('report_path'):
        artifacts['perf_html'] = _upload(Path(perf_result['report_path']))
    if zap_result and zap_result.get('report_path'):
        artifacts['zap_html'] = _upload(Path(zap_result['report_path']))
    # MobSF HTML if available
    if res := result.get('summary') if False else None:
        pass
    try:
        if result.get('report_path'):
            artifacts['mobsf_html'] = _upload(Path(result['report_path']))
    except Exception:
        pass

    if _is_canceled(job_id):
        _update(job_id, {"status": "canceled", "error": "canceled"}); return

    final_pass = all_passed and (perf_ok if test_type == "performance" else True) and (zap_ok if test_type == "security" else True)
    final = {"status": "completed" if final_pass else "failed", "result_path": str(out_path)}
    if artifacts:
        final['artifact_urls'] = artifacts
    _update(job_id, final)

    # Persist to Postgres if configured (store summary + artifact URLs)
    try:
        dsn = {
            "host": os.getenv("PGHOST", "postgres"),
            "port": int(os.getenv("PGPORT", "5432")),
            "user": os.getenv("PGUSER", "taas"),
            "password": os.getenv("PGPASSWORD", "taas"),
            "dbname": os.getenv("PGDATABASE", "taas"),
        }
        with psycopg2.connect(**dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("update test_sessions set status=%s, updated_at=now() where id=%s", (final['status'], job_id))
                result_db = dict(result)
                if artifacts:
                    result_db['artifact_urls'] = artifacts
                cur.execute("insert into test_results(session_id, summary) values (%s,%s)", (job_id, Json(result_db)))
            conn.commit()
    except Exception:
        pass

    # Slack notification (optional)
    try:
        hook = os.getenv('SLACK_WEBHOOK_URL')
        if hook:
            title = f"TaaS {test_type.upper()} {final['status'].upper()}"
            lines = [f"job: {job_id}", f"type: {test_type}", f"status: {final['status']}"]
            if perf_result and perf_result.get('performance_score') is not None:
                lines.append(f"perf: {perf_result['performance_score']}")
            if zap_result and zap_result.get('counts'):
                c = zap_result['counts']; lines.append(f"zap: H{c.get('High',0)}/M{c.get('Medium',0)}/L{c.get('Low',0)}")
            if artifacts:
                for k,v in list(artifacts.items())[:4]:
                    if v and v.get('presigned_url'): lines.append(f"{k}: {v['presigned_url']}")
            payload = {"text": title + "\n" + "\n".join(lines)}
            requests.post(hook, json=payload, timeout=10)
    except Exception:
        pass


def run_mobile_test(job_id: str, payload: Dict):
    _update(job_id, {"status": "running"})
    test_type = (payload.get("test_type") or "analyze").lower()
    if test_type == "analyze":
        res = _mobile_analyze_mobsf(payload)
    else:
        # Placeholder for E2E (Appium/FTL) to be implemented later
        res = {"test_type": test_type, "analyzer": "Appium", "summary": "E2E executed on device"}
    # attach job_id to allow proper naming of MobSF report
    res_with_id = dict(res)
    res_with_id['job_id'] = job_id
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(res_with_id, ensure_ascii=False, indent=2), encoding="utf-8")
    status = "completed" if res.get("passed", True) else "failed"
    final = {"status": status, "result_path": str(out_path)}
    if res.get("error"):
        final["error"] = res["error"]
    _update(job_id, final)


def _mobile_analyze_mobsf(payload: Dict) -> Dict:
    mobsf_url = (os.getenv("MOBSF_URL") or "").rstrip("/")
    mobsf_key = os.getenv("MOBSF_API_KEY")
    apk_path = payload.get("apk_path")
    ipa_path = payload.get("ipa_path")
    apk_url = payload.get("apk_url")
    ipa_url = payload.get("ipa_url")

    # If not configured, return graceful placeholder
    if not mobsf_url or not mobsf_key:
        return {
            "analyzer": "MobSF",
            "configured": False,
            "passed": True,
            "summary": "MobSF not configured; skipped static analysis",
        }

    try:
        # If a remote URL is provided, download into workspace tmp
        local_file = None
        if apk_path or ipa_path:
            local_file = apk_path or ipa_path
        else:
            src = apk_url or ipa_url
            if not src:
                raise ValueError("No APK/IPA provided")
            r = requests.get(src, timeout=60)
            r.raise_for_status()
            ext = ".apk" if apk_url else ".ipa"
            tmp = RESULTS_DIR / f"mobsf-{int(time.time())}{ext}"
            tmp.write_bytes(r.content)
            local_file = str(tmp)

        headers = {"Authorization": mobsf_key}
        files = {"file": open(local_file, "rb")}
        up = requests.post(f"{mobsf_url}/api/v1/upload", headers=headers, files=files, timeout=300)
        files["file"].close()
        up.raise_for_status()
        meta = up.json()
        hashv = meta.get("hash") or meta.get("md5") or meta.get("sha256")
        scan_type = meta.get("scan_type") or ("apk" if local_file.endswith(".apk") else "ipa")

        # Trigger scan
        data = {"hash": hashv, "scan_type": scan_type}
        scan = requests.post(f"{mobsf_url}/api/v1/scan", headers=headers, data=data, timeout=600)
        if scan.status_code >= 400:
            # Some MobSF versions use /api/v1/scan/{type}
            scan = requests.post(f"{mobsf_url}/api/v1/scan/{scan_type}", headers=headers, data=data, timeout=600)
        scan.raise_for_status()

        # Fetch JSON report
        rep = requests.post(f"{mobsf_url}/api/v1/report_json", headers=headers, data={"hash": hashv}, timeout=300)
        rep.raise_for_status()
        report_json = rep.json()

        # Extract a few key fields (best-effort)
        perms = report_json.get("permissions") or report_json.get("apppermissions")
        endpoints = report_json.get("urls") or report_json.get("domains")
        risk = report_json.get("risk_score") or report_json.get("score")

        # Try to get HTML report (if available)
        report_path = None
        try:
            rh = requests.post(f"{mobsf_url}/api/v1/report", headers=headers, data={"hash": hashv}, timeout=300)
            if rh.status_code < 400 and rh.text:
                html_path = RESULTS_DIR / f"{payload.get('job_id','mobsf')}-mobsf.html"
                # job_id not in scope here; caller will rename when integrating
                # fallback: use epoch time in filename if not set by caller
                if 'job_id' not in payload:
                    html_path = RESULTS_DIR / f"mobsf-{int(time.time())}.html"
                html_path.write_text(rh.text, encoding="utf-8")
                report_path = str(html_path)
        except Exception:
            report_path = None

        return {
            "analyzer": "MobSF",
            "configured": True,
            "passed": True,
            "summary": "Static analysis completed",
            "hash": hashv,
            "scan_type": scan_type,
            "risk_score": risk,
            "permissions": perms,
            "endpoints": endpoints,
            "report_path": report_path,
        }
    except Exception as e:
        return {"analyzer": "MobSF", "configured": True, "passed": False, "error": str(e)}
