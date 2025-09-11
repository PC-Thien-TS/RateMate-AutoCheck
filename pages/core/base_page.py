from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class BasePage:
    """Lightweight base page with common helpers.

    - Normalizes `base_url`
    - Provides `goto_path` with consistent waiting
    - Small wait helper for minor UI stabilization
    """

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = (base_url or "").rstrip("/")

    def goto_path(self, path: str, wait_until: str = "domcontentloaded", timeout: int = 30_000):
        p = (path or "/").strip()
        if not p.startswith("/"):
            p = "/" + p
        self.page.goto(f"{self.base_url}{p}", wait_until=wait_until, timeout=timeout)

    def wait_briefly(self, ms: int = 200):
        try:
            self.page.wait_for_timeout(ms)
        except Exception:
            pass

