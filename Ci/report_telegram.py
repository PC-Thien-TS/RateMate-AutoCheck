#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import pathlib
import xml.etree.ElementTree as ET


def _fmt_duration(sec):
    try:
        s = float(sec or 0.0)
    except Exception:
        s = 0.0
    if s < 60:
        return f"~{s:.1f}s"
    m = int(s // 60)
    s = int(s % 60)
    if m < 60:
        return f"~{m}m{s:02d}s"
    h = m // 60
    m = m % 60
    return f"~{h}h{m:02d}m"


def _extract_browser(name: str) -> str | None:
    # ví dụ: test_login[chromium] hoặc test_open_links_ok[webkit-/en/login]
    if not name:
        return None
    m = re.search(r"\[([^\]]+)\]", name)
    if not m:
        return None
    token = m.group(1)
    # tách trường hợp "chromium-/en/login"
    browser = token.split("-", 1)[0].strip().lower()
    if browser in ("chromium", "firefox", "webkit"):
        return browser
    return None


def _parse_all_testsuites(root):
    """Trả về danh sách (testsuite_element, browser_buckets) và tổng hợp overall."""
    suites = []
    overall = {
        "total": 0, "fail": 0, "error": 0, "skip": 0, "duration": 0.0,
        "fails": [], "slow": [], "per_browser": {"chromium": {"total": 0, "fail": 0, "error": 0, "skip": 0},
                                                 "firefox":  {"total": 0, "fail": 0, "error": 0, "skip": 0},
                                                 "webkit":   {"total": 0, "fail": 0, "error": 0, "skip": 0}}
    }

    def gi(elem, k, default=0):
        v = elem.get(k)
        if v is None or v == "":
            return default
        try:  # int hoặc float chuyển được
            return int(float(v))
        except Exception:
            return default

    # Lấy tất cả testsuite (root có thể là <testsuite> hoặc <testsuites>)
    if root.tag.endswith("testsuite"):
        ts_elems = [root]
    else:
        ts_elems = list(root.findall(".//testsuite"))
    if not ts_elems:
        return overall

    for ts in ts_elems:
        total = gi(ts, "tests")
        fail = gi(ts, "failures")
        error = gi(ts, "errors")
        skip = gi(ts, "skipped")
        try:
            duration = float(ts.get("time", "0") or 0.0)
        except Exception:
            duration = 0.0

        overall["total"] += total
        overall["fail"] += fail
        overall["error"] += error
        overall["skip"] += skip
        overall["duration"] += duration

        # duyệt testcase để build fails + slow + per-browser
        for tc in ts.findall(".//testcase"):
            name = (tc.get("name") or "").strip()
            classname = (tc.get("classname") or "").strip()
            full_name = f"{classname}.{name}".strip(".")
            # per-browser bucket
            b = _extract_browser(name) or _extract_browser(classname)
            # thời gian
            try:
                ttime = float(tc.get("time", "0") or 0.0)
            except Exception:
                ttime = 0.0
            if ttime > 0:
                overall["slow"].append((ttime, full_name))

            # kết quả lỗi/thất bại/skip
            fe = tc.find("failure") or tc.find("error")
            sk = tc.find("skipped")
            if b in overall["per_browser"]:
                overall["per_browser"][b]["total"] += 1
                if fe is not None:
                    # phân loại error/failure: nếu tag là <error> thì cộng error, còn lại failure
                    if fe.tag.endswith("error"):
                        overall["per_browser"][b]["error"] += 1
                    else:
                        overall["per_browser"][b]["fail"] += 1
                elif sk is not None:
                    overall["per_browser"][b]["skip"] += 1
            # thu thập lý do fail/error
            if fe is not None:
                msg = (fe.get("message") or "").strip()
                txt = (fe.text or "").strip()
                reason = (msg or txt or "No message").replace("\x00", "")
                overall["fails"].append({"name": full_name, "reason": reason[:400]})
            elif sk is not None:
                # không đẩy skip vào fails, chỉ đếm
                pass
            else:
                # passed: không thu thập
                pass

    # Sắp xếp slow tests, lấy top 5
    overall["slow"].sort(key=lambda x: x[0], reverse=True)
    overall["slow"] = overall["slow"][:5]
    return overall


def _parse_junit(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return {}
    try:
        root = ET.parse(p).getroot()
        return _parse_all_testsuites(root)
    except Exception as e:
        print(f"[report] WARN: failed to parse JUnit XML: {e}")
        return {}


def _load_summary():
    raw = (os.getenv("SUMMARY_JSON") or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            # nếu workflow đã parse sẵn và hợp lệ, dùng luôn
            if isinstance(data, dict) and data.get("total") is not None:
                return data
        except Exception as e:
            print(f"[report] WARN: SUMMARY_JSON parse error: {e}")

    junit_path = os.getenv("JUNIT_XML", "report/junit.xml")
    return _parse_junit(junit_path) or {}


def _build_header(summary):
    total = int(summary.get("total", 0))
    fail = int(summary.get("fail", 0))
    error = int(summary.get("error", 0))
    skip = int(summary.get("skip", 0))
    dur = float(summary.get("duration", 0.0))
    passed = max(total - fail - error - skip, 0)
    ok = (fail == 0 and error == 0)
    status = "✅" if ok else "❌"

    # context
    site = os.getenv("SITE", "") or os.getenv("PROJECT", "")
    env = os.getenv("ENV", "")
    base_url = os.getenv("BASE_URL", "") or os.getenv("BASE_URL_PROD", "")
    prefix = os.getenv("TELEGRAM_MESSAGE_PREFIX", "").strip()

    server = os.getenv("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.getenv("GITHUB_REPOSITORY", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else ""

    ref = os.getenv("GITHUB_REF_NAME", "") or os.getenv("GITHUB_REF", "")
    sha = os.getenv("GITHUB_SHA", "")
    short_sha = sha[:7] if sha else ""
    commit_url = f"{server}/{repo}/commit/{sha}" if repo and sha else ""

    head = []
    if prefix:
        head.append(prefix)

    title = f"{status} E2E Result: {total} tests | pass={passed} fail={fail} error={error} skip={skip}"
    head.append(title)
    head.append(f"Duration: {_fmt_duration(dur)}")

    context_bits = []
    if site:
        context_bits.append(f"SITE={site}")
    if env:
        context_bits.append(f"ENV={env}")
    if base_url:
        context_bits.append(f"BASE={base_url}")
    if ref:
        context_bits.append(f"BRANCH={ref}")
    if short_sha:
        context_bits.append(f"SHA={short_sha}")
    if context_bits:
        head.append(" · ".join(context_bits))

    if run_url:
        head.append(f"Run: {run_url}")
    if commit_url and short_sha:
        head.append(f"Commit: {commit_url}")

    return "\n".join(head)


def _build_browser_breakdown(summary):
    per = summary.get("per_browser") or {}
    if not per:
        return ""
    lines = ["", "Per-browser:"]
    for b in ("chromium", "firefox", "webkit"):
        if b in per:
            t = per[b].get("total", 0)
            f = per[b].get("fail", 0)
            e = per[b].get("error", 0)
            s = per[b].get("skip", 0)
            p = max(t - f - e - s, 0)
            lines.append(f"- {b}: {t} | pass={p} fail={f} error={e} skip={s}")
    return "\n".join(lines)


def _build_failures(summary):
    fails = summary.get("fails") or []
    if not fails:
        return ""
    lines = ["", "Failed cases (top 5):"]
    for i, f in enumerate(fails[:5], 1):
        nm = f.get("name", "")
        rs = (f.get("reason", "") or "").replace("\n", " ")[:300]
        lines.append(f"{i}. {nm} — {rs}")
    return "\n".join(lines)


def _build_slowest(summary):
    slow = summary.get("slow") or []
    if not slow:
        return ""
    lines = ["", "Slowest tests (top 5):"]
    for t, full in slow[:5]:
        lines.append(f"- {full} — {_fmt_duration(t)}")
    return "\n".join(lines)


def _build_message(summary):
    blocks = [
        _build_header(summary),
        "",
        f"Passed: {max(int(summary.get('total', 0)) - int(summary.get('fail', 0)) - int(summary.get('error', 0)) - int(summary.get('skip', 0)), 0)} case(s)",
        _build_browser_breakdown(summary),
        _build_failures(summary),
        _build_slowest(summary),
    ]
    text = "\n".join([b for b in blocks if b is not None and str(b).strip() != ""]).strip()
    return text if text else "No test results found."


def _prepare_proxies():
    px = os.getenv("TELEGRAM_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    if not px:
        return None
    if not (px.startswith("http://") or px.startswith("https://") or px.startswith("socks")):
        px = "http://" + px
    return {"http": px, "https": px}


def _send_text(text):
    import requests

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_env = os.environ["TELEGRAM_CHAT_ID"]
    chat_ids = [c.strip() for c in re.split(r"[,\s]+", chat_env) if c.strip()]
    proxies = _prepare_proxies()

    # preview
    print("\n===== Telegram message preview =====\n")
    print(text)
    print()

    CHUNK = 3900  # Telegram ~4096
    parts = [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)] or [text]

    for chat in chat_ids:
        sent = 0
        for idx, body in enumerate(parts, 1):
            data = {
                "chat_id": chat,
                "text": body,
                "disable_web_page_preview": True,
            }
            print(f"[telegram] Sending chunk {idx}/{len(parts)} to {chat} with proxy...")
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=data,
                    timeout=30,
                    proxies=proxies,
                )
                r.raise_for_status()
                print(f"[telegram] Chunk {idx} sent successfully")
                sent += 1
            except Exception as e:
                print(f"[telegram] Proxy send failed for chunk {idx}: {e}")
                print(f"[telegram] Retrying direct...")
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=data,
                    timeout=60,
                )
                r.raise_for_status()
                print(f"[telegram] Chunk {idx} sent successfully")
                sent += 1
        print(f"Telegram sent OK to {chat} ({sent}/{len(parts)} chunks).")


def main():
    s = _load_summary()
    if not s:
        print("[report] NOTE: No summary found; defaulting to zeros.")
        s = {"total": 0, "fail": 0, "error": 0, "skip": 0, "duration": 0.0,
             "fails": [], "per_browser": {}, "slow": []}
    msg = _build_message(s)
    _send_text(msg)


if __name__ == "__main__":
    main()
