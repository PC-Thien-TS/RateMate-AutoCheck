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

    per_browser = {b: {"total": 0, "fail": 0, "error": 0, "skip": 0} for b in ("chromium","firefox","webkit")}
    fails, passed, errored, skipped = [], [], [], []
    total = fail = error = skip = 0
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
            if ttime > 0:
                slow.append((ttime, full_name))

            fe = tc.find("failure")
            er = tc.find("error")
            sk = tc.find("skipped")

            status = "pass"
            if er is not None:
                status = "error"
                error += 1
                msg  = (er.get("message") or "").strip() or (er.text or "").strip() or "No message"
                fails.append({"name": full_name, "reason": msg[:400]})
                errored.append((full_name, ttime))
            elif fe is not None:
                status = "fail"
                fail += 1
                msg  = (fe.get("message") or "").strip() or (fe.text or "").strip() or "No message"
                fails.append({"name": full_name, "reason": msg[:400]})
                passed  # just to keep linter happy
                # Note: fail list already captured; also track in failed bucket
            elif sk is not None:
                status = "skip"
                skip += 1
                skipped.append((full_name, ttime))
            else:
                passed.append((full_name, ttime))

            total += 1

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
    return {
        "total": total, "fail": fail, "error": error, "skip": skip,
        "duration": duration_sum,
        "fails": fails, "per_browser": per_browser, "slow": slow[:5],
        "passed": passed, "failed": [(f["name"], 0.0) for f in fails], "errored": errored, "skipped": skipped,
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
    sha = os.getenv("GITHUB_SHA", ""); short_sha = sha[:7] if sha else ""
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

def _bullets(rows, limit=20):
    rows = rows[:limit]
    return "\n".join(f"• {name}" for name, _ in rows) if rows else "(none)"

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

def _build_message(summary):
    total = int(summary.get("total", 0))
    passed_n = max(total - int(summary.get("fail",0)) - int(summary.get("error",0)) - int(summary.get("skip",0)), 0)

    blocks = [
        _build_header(summary),
        "",
        f"Passed: {passed_n} case(s)",
    ]

    # liệt kê tên test
    passed  = summary.get("passed")  or []
    failed  = summary.get("failed")  or []
    errored = summary.get("errored") or []
    skipped = summary.get("skipped") or []

    if passed:
        blocks += ["", "✅ Passed (top 20):", _bullets(passed, 20)]
    if failed:
        blocks += ["", "❌ Failed:", _bullets(failed, 20)]
    if errored:
        blocks += ["", "💥 Errors:", _bullets(errored, 20)]
    if skipped:
        blocks += ["", "⚠️ Skipped:", _bullets(skipped, 20)]

    # breakdown + slowest
    br = _build_browser_breakdown(summary)
    if br:
        blocks += ["", br]
    slow = summary.get("slow") or []
    if slow:
        blocks += ["", "Slowest tests (top 5):"] + [f"- {full} — {_fmt_duration(t)}" for t, full in slow[:5]]

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
            data = {"chat_id": chat, "text": body, "disable_web_page_preview": True}
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
             "fails": [], "per_browser": {}, "slow": [],
             "passed": [], "failed": [], "errored": [], "skipped": [], "_junit_src": ""}
    msg = _build_message(s)
    _send_text(msg)

if __name__ == "__main__":
    main()
