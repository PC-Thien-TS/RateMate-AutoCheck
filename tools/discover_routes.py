#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lightweight route discovery for Playwright E2E.

Usage examples:
  # Minimal: let the script infer base_url + start path from a full URL
  python tools/discover_routes.py --url https://example.com/login

  # Explicit base_url and start path
  python tools/discover_routes.py --base https://example.com --start /login

Environment (optional):
  E2E_EMAIL / E2E_PASSWORD  Credentials to attempt login if a form is detected.
  SITE                      Site key for output file name (default: auto from host)
  LOGIN_PATH                Known login path to detect redirects (optional)

Output:
  Writes JSON to config/discovered/<site>.json with keys:
    base_url, login_path, public, protected
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
import urllib.parse as up
from collections import deque
from pathlib import Path

from playwright.sync_api import sync_playwright


def norm_base(url: str) -> str:
    p = up.urlparse(url)
    scheme = p.scheme or "https"
    netloc = p.netloc
    return f"{scheme}://{netloc}".rstrip("/")


def norm_path(path: str) -> str:
    if not path:
        return "/"
    if path.startswith("http://") or path.startswith("https://"):
        return up.urlparse(path).path or "/"
    return ("/" + path.lstrip("/")).split("#", 1)[0]


def guess_site(base: str) -> str:
    host = (up.urlparse(base).netloc or "site").lower()
    return re.sub(r"[^a-z0-9_\-]", "_", host)


def try_login(page, base_url: str, login_path: str | None, email: str | None, password: str | None):
    if not (email and password):
        return False
    # Heuristics for login form
    try:
        if login_path:
            page.goto(f"{base_url}{norm_path(login_path)}", wait_until="domcontentloaded", timeout=12_000)
        # Fill user & pass
        user = page.locator("input[type='email'], input[name*='user' i], input[id*='user' i], input[name*='account' i]").first
        pwd = page.locator("input[type='password']").first
        if user.count() == 0 or pwd.count() == 0:
            return False
        user.fill(email)
        pwd.fill(password)
        # Submit
        submit = page.get_by_role("button", name=re.compile(r"(login|log\s*in|sign\s*in|continue|submit)", re.I)).first
        if submit.count() == 0:
            submit = page.locator("button[type='submit'], input[type='submit']").first
        if submit.count():
            submit.click()
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
        # If we are not at login page anymore assume success
        cur = page.url
        return (not re.search(r"/log[-_]?in|/sign[-_]?in", up.urlparse(cur).path, re.I))
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Full start URL (infers base + start)")
    ap.add_argument("--base", help="Base URL (e.g., https://host)")
    ap.add_argument("--start", help="Start path (e.g., /login)")
    ap.add_argument("--max", type=int, default=40, help="Max pages to visit (default 40)")
    ap.add_argument("--depth", type=int, default=2, help="Max crawl depth (default 2)")
    ap.add_argument("--out", help="Output JSON path (default config/discovered/<site>.json)")
    args = ap.parse_args(argv)

    if args.url and (args.base or args.start):
        print("[discover] Use either --url or --base/--start, not both", file=sys.stderr)
        return 2

    if args.url:
        p = up.urlparse(args.url)
        base_url = f"{p.scheme}://{p.netloc}".rstrip("/")
        start = p.path or "/"
    else:
        if not args.base:
            print("[discover] Require --url or --base", file=sys.stderr)
            return 2
        base_url = norm_base(args.base)
        start = norm_path(args.start or "/")

    site = (os.getenv("SITE") or "").strip() or guess_site(base_url)
    login_path_env = os.getenv("LOGIN_PATH") or None
    ignore_patterns = [r"/logout", r"/sign[-_]?out", r"\.pdf$", r"\.jpg$", r"\.png$", r"\.svg$"]
    ignore_re = re.compile("|".join(ignore_patterns), re.I)

    email = os.getenv("E2E_EMAIL")
    password = os.getenv("E2E_PASSWORD")

    discovered_public: set[str] = set()
    discovered_protected: set[str] = set()

    visited: set[str] = set()
    q = deque([(start, 0)])

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # Try logging in once if credentials + login path known
        logged_in = try_login(page, base_url, login_path_env or start, email, password)
        if logged_in:
            print("[discover] Logged in successfully; will treat redirects to login as protected", file=sys.stderr)

        count = 0
        while q and count < args.max:
            path, depth = q.popleft()
            if path in visited or depth > args.depth:
                continue
            visited.add(path)
            count += 1
            try:
                resp = page.goto(f"{base_url}{path}", wait_until="domcontentloaded", timeout=12_000)
                status = resp.status if resp else None
                final_path = up.urlparse(page.url).path or "/"
                # Categorize
                is_login = bool(re.search(r"/log[-_]?in|/sign[-_]?in", final_path, re.I))
                if status in (401, 403) or is_login:
                    discovered_protected.add(path)
                else:
                    discovered_public.add(path)

                # Extract links
                hrefs = page.eval_on_selector_all(
                    "a[href]",
                    "nodes => nodes.map(n => n.getAttribute('href'))",
                )
                for href in hrefs or []:
                    if not href:
                        continue
                    if href.startswith("mailto:") or href.startswith("tel:"):
                        continue
                    u = up.urlparse(href)
                    if u.scheme and u.netloc and norm_base(href) != base_url:
                        continue  # external
                    pth = norm_path(u.path if u.scheme else href)
                    if ignore_re.search(pth):
                        continue
                    if pth not in visited:
                        q.append((pth, depth + 1))
            except Exception:
                # On navigation error consider path protected (may require auth) and continue
                discovered_protected.add(path)
                continue

        browser.close()

    # Prepare output
    out = {
        "base_url": base_url,
        "login_path": login_path_env or start,
        "public": sorted(x for x in discovered_public if x.startswith("/")),
        "protected": sorted(x for x in discovered_protected if x.startswith("/")),
    }

    out_dir = Path("config/discovered")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / f"{site}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[discover] Wrote {out_path}")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

