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
    m = int(s // 60)
    s = int(s % 60)
    if m < 60:
        return f"~{m}m{s:02d}s"
    h = m // 60
    m = m % 60
    return f"~{h}h{m:02d}m"


def _extract_browser(name: str) -> str | None:
    if not name:
        return None
    m = re.search(r"\[([^\]]+)\]", name)
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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except Exception:
        return default


# ---------- JUnit parsing ----------

def _find_junit():
    """Chọn đường dẫn JUnit hợp lệ:
       1) Ưu tiên env JUNIT_XML
       2) Fallback: file *.xml mới nhất trong report/ có chứa <testsuite>.
    """
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


def _parse_junit_any(path):
    """Đếm theo từng testcase để chắc số liệu, gom pass/fail/error/skip, top slow."""
    p = pathlib.Path(path)
    if not p.is_file():
        return {}

    try:
        root = ET.parse(p).getroot()
    except Exception as e:
        print(f"[report] WARN: parse error: {e}")
        return {}

    # Lấy tất cả testsuite
    if root.tag.endswith("testsuite"):
        suites = [root]
    else:
        suites = list(root.findall(".//testsuite"))
    if not suites:
        return {}

    per_browser = {"chromium": {"total": 0, "fail": 0, "error": 0, "skip": 0},
                   "firefox":  {"total": 0, "fail": 0, "error": 0, "skip": 0},
                   "webkit":   {"total": 0, "fail": 0, "error": 0, "skip": 0}}
    fails = []
    passed_cases = []
    slow = []
    total = fail = error = skip = 0
    duration_sum = 0.0

    for ts in suites:
        for tc in ts.findall(".//testcase"):
            name = (tc.get("name") or "").strip()
            classname = (tc.get("classname") or "").strip()
            if not name and not classname:
                # testcase thiếu dữ liệu — bỏ qua
                continue
            full_name = f"{classname}.{name}".strip(".")

            # thời gian
            try:
                ttime = float(tc.get("time", "0") or 0.0)
            except Exception:
                ttime = 0.0
            if ttime > 0:
                duration_sum += ttime
                slow.append((ttime, full_name))

            # trạng thái
            fe = tc.find("failure")
            er = tc.find("error")
            sk = tc.find("skipped")

            status = "pass"
            reason = ""
            if er is not None:
                status = "error"
                error += 1
                msg = (er.get("message") or "").strip()
                txt = (er.text or "").strip()
                reason = (msg or txt or "No message").replace("\x00", "")
                fails.append({"name": full_name, "reason": reason[:400]})
            elif fe is not None:
                status = "fail"
                fail += 1
                msg = (fe.get("message") or "").strip()
                txt = (fe.text or "").strip()
                reason = (msg or txt or "No message").replace("\x00", "")
                fails.append({"name": full_name, "reason": reason[:400]})
            elif sk is not None:
                status = "skip"
                skip += 1
            else:
                # pass
                passed_cases.append(full_name)

            total += 1

            # per-browser
            b = _extract_browser(name) or _extract_browser(classname)
            if b in per_browser:
                per_browser[b]["total"] += 1
                if status == "fail":
                    per_browser[b]["fail"] += 1
                elif status == "error":
                    per_browser[b]["error"] += 1
                elif status == "skip":
                    per_browser[b]["skip"] += 1

    slow.sort(key=lambda x: x[0], reverse=True)
    slow = slow[:_env_int("TELEGRAM_MAX_SLOW", 5)]

    return {
        "total": total,
        "fail": fail,
        "error": error,
        "skip": skip,
        "duration": duration_sum,  # dùng tổng testcase (ổn định hơn)
        "fails": fails,
        "passed_cases": passed_cases,
        "per_browser": per_browser,
        "slow": slow,
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
    fail = int(summary.get("fail", 0))
    error = int(summary.get("error", 0))
    skip = int(summary.get("skip", 0))
    dur = float(summary.get("duration", 0.0))
    passed = max(total - fail - error - skip, 0)
    ok = (fail == 0 and error == 0 and total > 0)
    status = "✅" if ok else "❌" if total > 0 else "⚠️"

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

    head.append(f"{status} E2E Result: {total} tests | pass={passed} fail={fail} error={error} skip={skip}")
    head.append(f"Duration: {_fmt_duration(dur)}")
    ctx = []
    if site: ctx.append(f"SITE={site}")
    if env: ctx.append(f"ENV={env}")
    if base_url: ctx.append(f"BASE={base_url}")
    if ref: ctx.append(f"BRANCH={ref}")
    if short_sha: ctx.append(f"SHA={short_sha}")
    if ctx:
        head.append(" · ".join(ctx))
    if run_url:
        head.append(f"Run: {run_url}")
    if commit_url and short_sha:
        head.append(f"Commit: {commit_url}")

    junit_src = summary.get("_junit_src")
    if junit_src:
        head.append(f"JUnit source: {junit_src}")

    if total == 0:
        head.append("No testcases detected — JUnit missing/empty or tests crashed before reporting.")
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
    limit = _env_int("TELEGRAM_MAX_FAILS", 5)
    lines = ["", f"Failed cases (top {min(limit, len(fails))}):"]
    for i, f in enumerate(fails[:limit], 1):
        nm = f.get("name", "")
        rs = (f.get("reason", "") or "").replace("\n", " ")[:300]
        lines.append(f"{i}. {nm} — {rs}")
    rest = len(fails) - limit
    if rest > 0:
        lines.append(f"... and {rest} more.")
    return "\n".join(lines)


def _build_passed(summary):
    passed = summary.get("passed_cases") or []
    if not passed:
        return ""
    limit = _env_int("TELEGRAM_MAX_PASSED", 10)
    lines = ["", f"Passed cases (first {min(limit, len(passed))}):"]
    for nm in passed[:limit]:
        lines.append(f"- {nm}")
    rest = len(passed) - limit
    if rest > 0:
        lines.append(f"... and {rest} more.")
    return "\n".join(lines)


def _build_slowest(summary):
    slow = summary.get("slow") or []
    if not slow:
        return ""
    lines = ["", "Slowest tests (top {n}):".format(n=len(slow))]
    for t, full in slow:
        lines.append(f"- {full} — {_fmt_duration(t)}")
    return "\n".join(lines)


def _build_message(summary):
    passed_count = max(int(summary.get('total', 0)) - int(summary.get('fail', 0)) - int(summary.get('error', 0)) - int(summary.get('skip', 0)), 0)
    blocks = [
        _build_header(summary),
        "",
        f"Passed: {passed_count} case(s)",
        _build_browser_breakdown(summary),
        _build_failures(summary),
        _build_passed(summary),
        _build_slowest(summary),
    ]
    return "\n".join([b for b in blocks if str(b).strip() != ""]).strip()


# ---------- telegram ----------

def _send_text(text):
    import requests

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_env = os.environ["TELEGRAM_CHAT_ID"]
    chat_ids = [c.strip() for c in re.split(r"[,\s]+", chat_env) if c.strip()]
    proxies = _prepare_proxies()

    print("\n===== Telegram message preview =====\n")
    print(text)
    print()

    CHUNK = 3900
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
                    data=data, timeout=30, proxies=proxies
                )
                r.raise_for_status()
                print(f"[telegram] Chunk {idx} sent successfully")
                sent += 1
            except Exception as e:
                print(f"[telegram] Proxy send failed for chunk {idx}: {e}")
                print("[telegram] Retrying direct...")
                r = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=data, timeout=60
                )
                r.raise_for_status()
                print(f"[telegram] Chunk {idx} sent successfully")
                sent += 1
        print(f"Telegram sent OK to {chat} ({sent}/{len(parts)} chunks).")


def main():
    s = _load_summary()
    if not s:
        print("[report] NOTE: No JUnit found. Sending minimal message.")
        s = {"total": 0, "fail": 0, "error": 0, "skip": 0, "duration": 0.0,
             "fails": [], "passed_cases": [], "per_browser": {}, "slow": [], "_junit_src": ""}
    msg = _build_message(s)
    _send_text(msg)


if __name__ == "__main__":
    main()
