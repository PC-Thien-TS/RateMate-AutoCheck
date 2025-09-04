# Ci/report_telegram.py
from __future__ import annotations
import os, sys, json, re
import xml.etree.ElementTree as ET
from pathlib import Path
import requests

JUNIT = os.getenv("JUNIT_XML") or "report/junit.xml"
SERVER = os.getenv("GITHUB_SERVER_URL", "https://github.com")
REPO   = os.getenv("GITHUB_REPOSITORY", "")
RUN_ID = os.getenv("GITHUB_RUN_ID", "")
REPORT_URL = f"{SERVER}/{REPO}/actions/runs/{RUN_ID}" if REPO and RUN_ID else ""

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")
MAX_TG_LEN = 4000

def _short(txt: str, lim: int = 220) -> str:
    if not txt:
        return ""
    first = None
    for line in txt.splitlines():
        s = line.strip()
        if not s:
            continue
        first = s
        if "AssertionError" in s or s.startswith("E "):
            break
    s = (first or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s[:lim]

def parse_junit(path: str):
    p = Path(path)
    if not p.exists():
        return {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}, [], [], []
    root = ET.parse(p).getroot()
    suites = [root] if root.tag.endswith("testsuite") else root.findall(".//testsuite")
    summary = dict(tests=0, failures=0, errors=0, skipped=0, time=0.0)
    fails, errs, passes = [], [], []
    for s in suites:
        summary["tests"]    += int(s.attrib.get("tests", 0))
        summary["failures"] += int(s.attrib.get("failures", 0))
        summary["errors"]   += int(s.attrib.get("errors", 0))
        summary["skipped"]  += int(s.attrib.get("skipped", 0))
        try:
            summary["time"] += float(s.attrib.get("time", 0.0))
        except Exception:
            pass
        for tc in s.findall("testcase"):
            name = tc.attrib.get("name", "")
            cls  = tc.attrib.get("classname", "")
            full = f"{cls}::{name}" if cls else name
            fail = tc.find("failure")
            err  = tc.find("error")
            skp  = tc.find("skipped")
            if fail is not None:
                msg = fail.attrib.get("message") or (fail.text or "")
                fails.append({"name": full, "why": _short(msg)})
            elif err is not None:
                msg = err.attrib.get("message") or (err.text or "")
                errs.append({"name": full, "why": _short(msg)})
            elif skp is not None:
                pass
            else:
                passes.append(full)
    return summary, fails, errs, passes

def format_message(summary, fails, errs, passes, report_url=""):
    ok = (summary["failures"] == 0 and summary["errors"] == 0)
    emoji = "✅" if ok else "❌"
    passed_count = summary['tests'] - summary['failures'] - summary['errors'] - summary['skipped']
    lines = [
        f"{emoji} E2E Result: {summary['tests']} tests | "
        f"pass={passed_count} fail={summary['failures']} error={summary['errors']} skip={summary['skipped']}",
        f"Duration: ~{summary['time']:.1f}s",
    ]
    if report_url:
        lines.append(f"Run: {report_url}")
    if errs:
        lines.append("\n== Errors (lỗi hệ thống) ==")
        for e in errs[:20]:
            lines.append(f"• {e['name']}")
            if e['why']: lines.append(f"  ↳ {e['why']}")
    if fails:
        lines.append("\n== Failures (sai kỳ vọng) ==")
        for f in fails[:20]:
            lines.append(f"• {f['name']}")
            if f['why']: lines.append(f"  ↳ {f['why']}")
    lines.append(f"\nPassed: {passed_count} case(s)")
    return "\n".join(lines)

def _want_proxy() -> bool:
    """Bật/tắt proxy qua USE_TG_PROXY. Mặc định: nếu có TELEGRAM_PROXY thì dùng, ngược lại không."""
    val = os.getenv("USE_TG_PROXY")
    if val is not None:
        return val.strip().lower() in ("1", "true", "yes", "on")
    return bool(os.getenv("TELEGRAM_PROXY"))

def _proxy_dict():
    px = os.getenv("TELEGRAM_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not px:
        return None
    if not (px.startswith("http://") or px.startswith("https://") or px.startswith("socks")):
        px = "http://" + px
    return {"http": px, "https": px}

def _post_with_fallback(url: str, **kw):
    """
    Nếu đang bật proxy -> thử gửi qua proxy; lỗi thì retry 1 lần **không proxy**.
    Nếu không bật proxy -> gửi trực tiếp.
    """
    timeout = kw.pop("timeout", 45)
    session = requests.Session()
    session.trust_env = False  # bỏ qua proxy mặc định của runner (nếu có)
    if _want_proxy():
        try:
            r = session.post(url, timeout=timeout, proxies=_proxy_dict(), **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"[telegram] proxy failed ({e.__class__.__name__}), retrying direct...")
            # fall-through to direct
    r = session.post(url, timeout=timeout, **kw)
    r.raise_for_status()
    return r

def _send_chunked(text: str):
    if not TG_TOKEN or not TG_CHAT:
        print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not provided; skip sending.")
        print(text)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    parts, cur, size = [], [], 0
    for line in text.splitlines():
        if size + len(line) + 1 > MAX_TG_LEN and cur:
            parts.append("\n".join(cur)); cur, size = [], 0
        cur.append(line); size += len(line) + 1
    if cur: parts.append("\n".join(cur))
    for chunk in parts:
        payload = {"chat_id": TG_CHAT, "text": chunk, "disable_web_page_preview": True}
        _post_with_fallback(url, json=payload)
    print(f"Telegram sent OK ({len(parts)} message{'s' if len(parts) > 1 else ''}).")

def main():
    junit_path = sys.argv[1] if len(sys.argv) > 1 else JUNIT
    summary_json = os.getenv("SUMMARY_JSON")
    if summary_json:
        try:
            obj = json.loads(summary_json) if isinstance(summary_json, str) else summary_json
            summary = {
                "tests": int(obj.get("total", 0)),
                "failures": int(obj.get("fail", 0)),
                "errors": int(obj.get("error", 0)),
                "skipped": int(obj.get("skip", 0)),
                "time": float(obj.get("duration", 0.0)),
            }
            fails = [{"name": f.get("name", ""), "why": _short(f.get("reason", ""))} for f in obj.get("fails", [])]
            errs, passes = [], []
        except Exception:
            summary, fails, errs, passes = parse_junit(junit_path)
    else:
        summary, fails, errs, passes = parse_junit(junit_path)

    msg = format_message(summary, fails, errs, passes, REPORT_URL)
    print("\n===== Telegram message preview =====\n")
    print(msg, "\n")
    _send_chunked(msg)

if __name__ == "__main__":
    main()
