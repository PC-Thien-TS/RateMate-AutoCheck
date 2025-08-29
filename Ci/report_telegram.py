# ci/report_telegram.py
import os, re, sys, json
import xml.etree.ElementTree as ET
from pathlib import Path


try:
    import requests  # requirements.txt của bạn đã có requests
except Exception as e:
    print("Missing 'requests'. Install it or run inside your docker image.")
    raise

JUNIT = os.getenv("JUNIT_XML", "report/junit.xml")
REPORT_URL = os.getenv("GITHUB_SERVER_URL", "") + "/" + os.getenv("GITHUB_REPOSITORY", "") + "/actions/runs/" + os.getenv("GITHUB_RUN_ID", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

def _short(txt: str, lim: int = 220) -> str:
    if not txt:
        return ""
    # lấy dòng đầu (hoặc dòng đầu chứa 'AssertionError' / 'E ')
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

def parse_junit(p: str):
    p = Path(p)
    if not p.exists():
        raise FileNotFoundError(f"JUnit XML not found: {p}")
    root = ET.parse(p).getroot()
    # Hỗ trợ <testsuite> hoặc <testsuites>
    suites = []
    if root.tag == "testsuite":
        suites = [root]
    else:
        suites = root.findall(".//testsuite")
    summary = dict(tests=0, failures=0, errors=0, skipped=0, time=0.0)
    fails, errs, passes = [], [], []
    for s in suites:
        summary["tests"]    += int(s.attrib.get("tests", 0))
        summary["failures"] += int(s.attrib.get("failures", 0))
        summary["errors"]   += int(s.attrib.get("errors", 0))
        summary["skipped"]  += int(s.attrib.get("skipped", 0))
        try:
            summary["time"] += float(s.attrib.get("time", 0.0))
        except:
            pass
        for tc in s.findall("testcase"):
            name = tc.attrib.get("name", "")
            cls  = tc.attrib.get("classname", "")
            full = f"{cls}::{name}" if cls else name
            fail = tc.find("failure")
            err  = tc.find("error")
            skp  = tc.find("skipped")
            if fail is not None:
                msg = fail.attrib.get("message") or fail.text or ""
                fails.append({"name": full, "why": _short(msg)})
            elif err is not None:
                msg = err.attrib.get("message") or err.text or ""
                errs.append({"name": full, "why": _short(msg)})
            elif skp is not None:
                # bỏ qua; chỉ thống kê
                pass
            else:
                passes.append(full)
    return summary, fails, errs, passes

def format_message(summary, fails, errs, passes, report_url=""):
    ok = (summary["failures"] == 0 and summary["errors"] == 0)
    emoji = "✅" if ok else "❌"
    lines = []
    lines.append(f"{emoji} E2E Result: {summary['tests']} tests | "
                 f"pass={summary['tests']-summary['failures']-summary['errors']-summary['skipped']} "
                 f"fail={summary['failures']} error={summary['errors']} skip={summary['skipped']}")
    lines.append(f"Duration: ~{summary['time']:.1f}s")
    if report_url:
        lines.append(f"Run: {report_url}")
    if errs:
        lines.append("\n== Errors (lỗi hệ thống) ==")
        for e in errs[:20]:
            lines.append(f"• {e['name']}")
            if e['why']:
                lines.append(f"  ↳ {e['why']}")
    if fails:
        lines.append("\n== Failures (sai kỳ vọng) ==")
        for f in fails[:20]:
            lines.append(f"• {f['name']}")
            if f['why']:
                lines.append(f"  ↳ {f['why']}")
    # liệt kê pass ngắn gọn
    passed_count = summary['tests'] - summary['failures'] - summary['errors'] - summary['skipped']
    lines.append(f"\nPassed: {passed_count} case(s)")
    return "\n".join(lines)

def send_telegram(text: str):
    if not TG_TOKEN or not TG_CHAT:
        print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not provided; skip sending.")
        print(text)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20)
    if r.status_code >= 300:
        print("Telegram send failed:", r.status_code, r.text, file=sys.stderr)
    else:
        print("Telegram sent OK")

def _proxies():
    """
    Ưu tiên TELEGRAM_PROXY; fallback HTTPS_PROXY/HTTP_PROXY.
    Cho phép value là 'http://host:port' hoặc 'host:port'.
    """
    px = os.getenv("TELEGRAM_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not px:
        return None
    if not px.startswith("http://") and not px.startswith("https://") and not px.startswith("socks"):
        px = "http://" + px  # mặc định http proxy
    return {"http": px, "https": px}

def send_telegram(text: str):
    if not TG_TOKEN or not TG_CHAT:
        print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not provided; skip sending.")
        print(text)
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=30, proxies=_proxies())
        r.raise_for_status()
        print("Telegram sent OK")
    except Exception as e:
        print("Telegram send failed:", repr(e), file=sys.stderr)
        # in case proxy lỗi, in preview ra log
        print(text)
def main():
    summary, fails, errs, passes = parse_junit(JUNIT)
    msg = format_message(summary, fails, errs, passes, REPORT_URL)
    print("\n===== Telegram message preview =====\n")
    print(msg)
    send_telegram(msg)

if __name__ == "__main__":
    main()
