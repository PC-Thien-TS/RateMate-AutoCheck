#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from playwright.sync_api import sync_playwright


def main(base: str, path: str = "/") -> int:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context()
        p = ctx.new_page()
        p.goto(base.rstrip("/") + path, wait_until="domcontentloaded", timeout=30_000)
        try:
            p.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        p.wait_for_timeout(1200)
        inputs = p.eval_on_selector_all(
            "input",
            "els => els.map(e => ({type:e.type||'', name:e.name||'', id:e.id||'', ph:e.getAttribute('placeholder')||'', aria:e.getAttribute('aria-label')||'', role:e.getAttribute('role')||''}))",
        )
        import sys
        def out(s: str):
            try:
                sys.stdout.write(s + "\n")
            except Exception:
                try:
                    sys.stdout.buffer.write((s + "\n").encode("utf-8", errors="replace"))
                except Exception:
                    pass
        out("URL: " + str(p.url))
        out("Inputs:")
        for it in inputs or []:
            out(" - " + repr(it))
        # buttons
        names = []
        try:
            btns = p.get_by_role("button")
            n = min(btns.count(), 30)
            for i in range(n):
                el = btns.nth(i)
                try:
                    if el.is_visible(timeout=300):
                        names.append(el.inner_text(timeout=300) or "")
                except Exception:
                    pass
        except Exception:
            pass
        out("Buttons: " + repr([s for s in names if s and s.strip()]))
        try:
            anchors = p.eval_on_selector_all(
                "a[href]",
                "els => els.map(a => ({href:a.getAttribute('href')||'', text:(a.textContent||'').trim()}))",
            )
        except Exception:
            anchors = []
        out("Anchors: " + repr(anchors))
        try:
            ions = p.eval_on_selector_all(
                "ion-button, ion-router-link, ion-tab-button",
                "els => els.map(e => ({tag:e.tagName.toLowerCase(), text:(e.textContent||'').trim()}))",
            )
        except Exception:
            ions = []
        out("Ionic: " + repr(ions))
        # Try clicking Sign in
        try:
            si = p.locator("ion-button:has-text('Sign in')")
            if si.count() > 0:
                si.first.click()
                p.wait_for_timeout(800)
                inputs2 = p.eval_on_selector_all(
                    "input",
                    "els => els.map(e => ({type:e.type||'', name:e.name||'', id:e.id||'', ph:e.getAttribute('placeholder')||'', aria:e.getAttribute('aria-label')||'', role:e.getAttribute('role')||''}))",
                )
                out("After click - Inputs: " + repr(inputs2))
        except Exception as e:
            out("Sign in click error: " + repr(e))
        b.close()
    return 0


if __name__ == "__main__":
    import os, sys
    base = os.getenv("BASE_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")
    path = os.getenv("LOGIN_PATH") or (sys.argv[2] if len(sys.argv) > 2 else "/")
    if not base:
        print("Usage: BASE_URL=https://host LOGIN_PATH=/en/login python tools/debug_probe.py")
        sys.exit(2)
    raise SystemExit(main(base, path))
