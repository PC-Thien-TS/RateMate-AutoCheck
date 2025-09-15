#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import glob
import pathlib
import xml.etree.ElementTree as ET

# ---------- utils ----------

def _fmt_duration(sec):
    try:
        s = float(sec or 0.0)
    except Exception:
        s = 0.0
    if s < 60:
        return f"~{s:.1f}s"
    m = int(s // 60); s = int(s % 60)
    if m < 60:
        return f"~{m}m{s:02d}s"
    h = m // 60; m = m % 60
    return f"~{h}h{m:02d}m"

def _extract_browser(name: str) -> str | None:
    if not name:
        return None
    m = re.search(r"[^\[\]]+", name)
    if not m:
        return None
    token = m.group(1)
    browser = token.split("-", 1)[0].strip().lower()
    return browser if browser in ("chromium", "firefox", "webkit") else None

def _prepare_proxies():
    px = os.getenv("TELEGRAM_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not px:
        return None
    if not (px.startswith("http://") or px.startswith("https://") or px.startswith("socks")):
        px = "http://" + px
    return {"http": px, "https": px}

def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _pretty_test_id(name: str) -> str:
    if not name:
        return name
    base, br = (name.split("[", 1) + [""])[:2]
    br = br.rstrip("]") if br else ""
    parts = base.split(".")
    if parts and parts[0] == "tests":
        parts = parts[1:]
    mod = "/".join(parts[:-1]) if len(parts) > 1 else base
    fn = parts[-1] if parts else base
    browser = None
    param = None
    if br:
        if "-" in br:
            browser, param = br.split("-", 1)
        else:
            browser, param = br, None
    tail = []
    if param:
        tail.append(f"[{param}]")
    if browser:
        tail.append(f"({browser})")
    suffix = (" " + " ".join(tail)) if tail else ""
    return f"{mod}::{fn}{suffix}"

# ---------- JUnit parsing ----------

def _find_junit():
    p_env = (os.getenv("JUNIT_XML") or "").strip()
    if p_env and pathlib.Path(p_env).is_file():
        return p_env
    cands = sorted(glob.glob("report/*.xml"), key=lambda p: pathlib.Path(p).stat().st_mtime, reverse=True)
    for p in cands:
        try:
            root = ET.parse(p).getroot()
            if root.tag.endswith("testsuite") or root.find(".//testsuite") is not None:
                return p
        except Exception:
            continue
    return p_env or ""

def _collect_suites(root):
    return [root] if root.tag.endswith("testsuite") else list(root.findall(".//testsuite"))

def _parse_junit_any(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return {}
    try:
        root = ET.parse(p).getroot()
    except Exception as e:
        print(f"[report] WARN: parse error: {e}")
        return {}

    suites = _collect_suites(root)
    if not suites:
        return {}

    passed, errored, failed, skipped = [], [], [], []
    duration_sum = 0.0
    slow = []

    for ts in suites:
        try:
            duration_sum += float(ts.get("time","0") or 0.0)
        except Exception:
            pass
        for tc in ts.findall(".//testcase"):
            name = (tc.get("name") or "").strip()
            classname = (tc.get("classname") or "").strip()
            full_name = f"{classname}.{name}".strip(".")

            try:
                ttime = float(tc.get("time", "0") or 0.0)
            except Exception:
                ttime = 0.0
            if ttime > 5:
                slow.append((ttime, full_name))

            props = {p.get("name"): p.get("value") for p in tc.findall("properties/property")}
            cid = props.get("case_id", "")
            title = props.get("case_title", "")

            fe = tc.find("failure")
            er = tc.find("error")
            sk = tc.find("skipped")

            test_details = {'name': full_name, 'time': ttime, 'id': cid, 'title': title}

            if er is not None:
                msg = (er.get("message") or "").strip() or (er.text or "").strip() or "No message"
                test_details['reason'] = msg
                errored.append(test_details)
            elif fe is not None:
                msg = (fe.get("message") or "").strip() or (fe.text or "").strip() or "No message"
                test_details['reason'] = msg
                failed.append(test_details)
            elif sk is not None:
                msg = (sk.get("message") or "").strip() or (sk.text or "").strip() or ""
                test_details['reason'] = msg
                skipped.append(test_details)
            else:
                passed.append(test_details)

    slow.sort(key=lambda x: x[0], reverse=True)
    return {
        "total": len(passed) + len(failed) + len(errored) + len(skipped),
        "duration": duration_sum,
        "slow": slow[:5],
        "passed_tests": passed,
        "failed_tests": failed,
        "errored_tests": errored,
        "skipped_tests": skipped,
        "_junit_src": str(p),
    }

def _load_summary():
    raw = (os.getenv("SUMMARY_JSON") or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("total") is not None:
                return data
        except Exception as e:
            print(f"[report] WARN: SUMMARY_JSON parse error: {e}")
    path = _find_junit()
    if not path or not pathlib.Path(path).is_file():
        return {}
    return _parse_junit_any(path)

# ---------- message builders ----------

def _build_header(summary):
    total = int(summary.get("total", 0))
    passed = len(summary.get("passed_tests", []))
    failed = len(summary.get("failed_tests", []))
    errored = len(summary.get("errored_tests", []))
    skipped = len(summary.get("skipped_tests", []))
    dur = float(summary.get("duration", 0.0))

    ok = (failed == 0 and errored == 0 and total > 0)
    status = "✅" if ok else "❌" if total > 0 else "⚠️"

    site = os.getenv("SITE", "") or os.getenv("PROJECT", "")
    base_url = os.getenv("BASE_URL", "")
    prefix = os.getenv("TELEGRAM_MESSAGE_PREFIX", "").strip()

    server = os.getenv("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else ""

    ref = os.getenv("GITHUB_REF_NAME", "") or os.getenv("GITHUB_REF", "")
    sha = os.getenv("GITHUB_SHA", ""); short_sha = sha[:7] if sha else ""
    commit_url = f"{server}/{repo}/commit/{sha}" if repo and sha else ""

    head = []
    if prefix:
        head.append(prefix)

    head.append(f"{status} E2E Result: {total} tests | pass={passed} fail={failed} error={errored} skip={skipped}")
    head.append(f"Duration: {_fmt_duration(dur)}")
    
    ctx = []
    if site: ctx.append(f"SITE={site}")
    if base_url: ctx.append(f"BASE={base_url}")
    if ref: ctx.append(f"BRANCH={ref}")
    if short_sha: ctx.append(f"SHA={short_sha}")
    if ctx:
        head.append(" · ".join(ctx))
    if run_url:
        head.append(f"Run: {run_url}")

    if total == 0:
        head.append("No testcases detected — JUnit missing/empty or tests crashed before reporting.")
    return "\n".join(head)

def _build_message(summary):
    blocks = [_build_header(summary)]

    passed = summary.get("passed_tests", [])
    failed = summary.get("failed_tests", [])
    errored = summary.get("errored_tests", [])
    skipped = summary.get("skipped_tests", [])
    
    def format_test_list(tests, show_reason=False):
        lines = []
        tests.sort(key=lambda x: x.get('id') or x.get('name'))
        limit = _list_limit_from_env("TELEGRAM_LIST_LIMIT", 20)
        
        for test in tests[:limit]:
            case_id = test.get('id')
            title = test.get('title') or _pretty_test_id(test.get('name'))
            prefix = f"[{case_id}] " if case_id else "• "
            lines.append(f"{prefix}{title}")
            if show_reason and test.get('reason'):
                reason = test['reason'].split('\n')[0]
                lines.append(f"  └─ {reason[:200]}")
        
        more = len(tests) - limit
        if more > 0:
            lines.append(f"(...and {more} more)")
        return "\n".join(lines)

    if failed:
        blocks.append("\n❌ *Failed Tests:*")
        blocks.append(format_test_list(failed, show_reason=True))
    
    if errored:
        blocks.append("\n💥 *Errored Tests:*")
        blocks.append(format_test_list(errored, show_reason=True))

    if skipped:
        blocks.append("\n⚠️ *Skipped Tests:*")
        blocks.append(format_test_list(skipped, show_reason=True))

    show_passed = _bool_env("TELEGRAM_SHOW_PASSED", False)
    if passed and show_passed:
        blocks.append("\n✅ *Passed Tests:*")
        blocks.append(format_test_list(passed))

    slow = summary.get("slow") or []
    if slow:
        blocks.append("\n🐌 *Slowest tests (top 5):*")
        for t, full in slow[:5]:
            blocks.append(f"- {_fmt_duration(t)} — {_pretty_test_id(full)}")

    return "\n".join(filter(None, blocks))

# ---------- telegram ----------

def _list_limit_from_env(var_name: str, default: int = 20) -> int:
    try:
        v = int(os.getenv(var_name, str(default)) or default)
        return v if v > 0 else default
    except Exception:
        return default

def _send_text(text):
    import requests
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_env = os.environ["TELEGRAM_CHAT_ID"]
    chat_ids = [c.strip() for c in re.split(r"[\\s,]+", chat_env) if c.strip()]
    proxies = _prepare_proxies()

    print("\n===== Telegram message preview =====\n")
    print(text)
    print()

    CHUNK = 3900
    parts = [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)] or [text]

    for chat in chat_ids:
        sent = 0
        for idx, body in enumerate(parts, 1):
            data = {"chat_id": chat, "text": body, "disable_web_page_preview": True, "parse_mode": "Markdown"}
            print(f"[telegram] Sending chunk {idx}/{len(parts)} to {chat}...")
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=data, timeout=30, proxies=proxies
                )
                r.raise_for_status()
                print(f"[telegram] Chunk {idx} sent successfully")
                sent += 1
            except Exception as e:
                print(f"[telegram] Proxy send failed for chunk {idx}: {e}")
                print("[telegram] Retrying direct (without proxy)...")
                with requests.Session() as s:
                    s.trust_env = False
                    r = s.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        data=data, timeout=60, proxies={}
                    )
                    r.raise_for_status()
                    print(f"[telegram] Chunk {idx} sent successfully via direct connection.")
                    sent += 1
        print(f"Telegram sent OK to {chat} ({sent}/{len(parts)} chunks).")

def main():
    s = _load_summary()
    if not s:
        print("[report] NOTE: No JUnit found. Sending minimal message.")
        s = {"total": 0, "passed_tests": [], "failed_tests": [], "errored_tests": [], "skipped_tests": []}
    
    msg = _build_message(s)
    _send_text(msg)

if __name__ == "__main__":
    main()
