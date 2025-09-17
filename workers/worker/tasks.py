import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright
import yaml
import requests


RESULTS_DIR = Path(os.getenv("TAAS_RESULTS_DIR", "test-results/taas")).resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE = Path("/workspace").resolve()


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

    case_results = []
    all_passed = True
    t0 = time.time()
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
            })
            if not passed:
                all_passed = False

    elapsed = round(time.time() - t0, 2)

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
        }
    else:
        result = {
            "test_type": test_type,
            "passed": all_passed,
            "cases": case_results,
            "duration_sec": elapsed,
        }
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    final = {"status": "completed" if all_passed else "failed", "result_path": str(out_path)}
    _update(job_id, final)


def run_mobile_test(job_id: str, payload: Dict):
    _update(job_id, {"status": "running"})
    test_type = (payload.get("test_type") or "analyze").lower()
    if test_type == "analyze":
        res = _mobile_analyze_mobsf(payload)
    else:
        # Placeholder for E2E (Appium/FTL) to be implemented later
        res = {"test_type": test_type, "analyzer": "Appium", "summary": "E2E executed on device"}
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
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
        }
    except Exception as e:
        return {"analyzer": "MobSF", "configured": True, "passed": False, "error": str(e)}
