# Ci/report_telegram.py
import os, re, sys, json
import xml.etree.ElementTree as ET
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import requests
except Exception:
    print("Missing 'requests'. Please install it first.")
    raise

# ===== Env =====
JUNIT = os.getenv("JUNIT_XML") or "report/junit.xml"
REPORT_URL = (
    (os.getenv("GITHUB_SERVER_URL", "") + "/" + os.getenv("GITHUB_REPOSITORY", "") + "/actions/runs/" + os.getenv("GITHUB_RUN_ID", ""))
    if os.getenv("GITHUB_REPOSITORY") and os.getenv("GITHUB_RUN_ID")
    else ""
)
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT  = os.getenv("TELEGRAM_CHAT_ID")
MAX_TG_LEN = 4000  # < 4096

# ===== Helpers =====
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
        # Thử fallback: report/report/junit.xml (nếu lỡ copy thừa cấp)
        p2 = Path("report/report/junit.xml")
        if p2.exists():
            p = p2
        else:
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

    lines = []
    lines.append(
        f"{emoji} E2E Result: {summary['tests']} tests | "
        f"pass={passed_count} fail={summary['failures']} error={summary['errors']} skip={summary['skipped']}"
    )
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

    lines.append(f"\nPassed: {passed_count} case(s)")
    return "\n".join(lines)

def _proxies():
    px = os.getenv("TELEGRAM_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not px:
        return None
    if not (px.startswith("http://") or px.startswith("https://") or px.startswith("socks")):
        px = "http://" + px
    return {"http": px, "https": px}

def _send_chunked(text: str):
    if not TG_TOKEN or not TG_CHAT:
        print("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not provided; skip sending.")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    proxies = _proxies()

    parts, cur, size = [], [], 0
    for line in text.splitlines():
        if size + len(line) + 1 > MAX_TG_LEN and cur:
            parts.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        parts.append("\n".join(cur))

    successful_parts = 0
    
    # Tạo session với retry strategy
    session = requests.Session()
    
    # Thêm imports nếu chưa có (ở đầu file)
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    for i, chunk in enumerate(parts, 1):
        payload = {"chat_id": TG_CHAT, "text": chunk, "disable_web_page_preview": True}
        
        # Thử nhiều phương án kết nối
        attempts = [
            {"proxies": proxies, "timeout": 45, "desc": "with proxy"},
            {"proxies": None, "timeout": 60, "desc": "direct with longer timeout"},
            {"proxies": None, "timeout": 90, "desc": "direct with very long timeout"}
        ]
        
        for attempt in attempts:
            try:
                print(f"[telegram] Sending chunk {i}/{len(parts)} {attempt['desc']}...")
                r = session.post(
                    url, 
                    json=payload, 
                    timeout=attempt["timeout"],
                    proxies=attempt["proxies"]
                )
                r.raise_for_status()
                successful_parts += 1
                print(f"[telegram] Chunk {i} sent successfully")
                break
            except requests.exceptions.Timeout:
                print(f"[telegram] Timeout {attempt['desc']} for chunk {i}")
                continue
            except requests.exceptions.ProxyError:
                print(f"[telegram] Proxy error for chunk {i}, trying direct...")
                continue
            except Exception as e:
                print(f"[telegram] Error {attempt['desc']} for chunk {i}: {e}")
                continue
        else:
            print(f"[telegram] All attempts failed for chunk {i}")
    
    if successful_parts > 0:
        print(f"Telegram sent OK ({successful_parts}/{len(parts)} chunks).")
    else:
        print("Telegram sending failed completely.")
        # Không raise exception để tránh fail cả process

def main():
    junit_path = sys.argv[1] if len(sys.argv) > 1 else JUNIT
    summary_json = os.getenv("SUMMARY_JSON")

    summary = None; fails = []; errs = []; passes = []
    if summary_json:
        try:
            obj = json.loads(summary_json) if isinstance(summary_json, str) else summary_json
            # Nếu obj rỗng ({}), coi như KHÔNG có summary → fallback XML
            if obj and isinstance(obj, dict) and any(k in obj for k in ("total","tests")):
                summary = {
                    "tests": int(obj.get("total", obj.get("tests", 0))),
                    "failures": int(obj.get("fail", obj.get("failures", 0))),
                    "errors": int(obj.get("error", obj.get("errors", 0))),
                    "skipped": int(obj.get("skip", obj.get("skipped", 0))),
                    "time": float(obj.get("duration", obj.get("time", 0.0))),
                }
                fails = [{"name": f.get("name", ""), "why": _short(f.get("reason", ""))} for f in obj.get("fails", [])]
                errs, passes = [], []
        except Exception:
            summary = None

    if summary is None:
        summary, fails, errs, passes = parse_junit(junit_path)

    msg = format_message(summary, fails, errs, passes, REPORT_URL)
    print("\n===== Telegram message preview =====\n")
    print(msg, "\n")
    try:
        _send_chunked(msg)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        print("Continuing without Telegram notification...")
        # Không raise exception để process vẫn exit code 0 nếu test pass

if __name__ == "__main__":
    main()
