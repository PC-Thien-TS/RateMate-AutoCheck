# pages/sites/fuchacha/auth_login.py
from __future__ import annotations
import re
import time
from typing import Optional

from playwright.sync_api import Page, Locator
from pages.core.base_page import BasePage
from pages.common_helpers import ResponseLike


def _first_visible(scope: Locator | Page, selector: str | None = None, rx: re.Pattern | None = None, timeout_ms: int = 3000) -> Optional[Locator]:
    try:
        if isinstance(scope, Page):
            loc = scope.get_by_label(rx) if rx else scope.locator(selector)
        else:
            loc = scope.get_by_label(rx) if rx else scope.locator(selector)
        item = loc.first
        item.wait_for(state="visible", timeout=timeout_ms)
        return item
    except Exception:
        return None


class LoginPage(BasePage):
    """Login page tailored for Fuchacha UI (User Name + Password + Login).

    Keeps the same public API with generic LoginPage (goto/login returning ResponseLike).
    """

    def __init__(self, page: Page, base_url: str, login_path: str = "/login/pwd-login"):
        super().__init__(page, base_url)
        self.login_path = login_path if login_path.startswith("/") else f"/{login_path}"

    def goto(self):
        url = f"{self.base_url}{self.login_path}"
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_timeout(200)
        except Exception:
            pass

    def _username(self) -> Optional[Locator]:
        # Labels/placeholder typically 'User Name'
        rx = re.compile(r"user\s*name|username", re.I)
        el = _first_visible(self.page, rx=rx, timeout_ms=2500)
        if el:
            return el
        try:
            return self.page.get_by_placeholder(rx).first
        except Exception:
            pass
        # Fallback
        return self.page.locator("input[type='text'], input[name*='user' i]").first

    def _password(self) -> Optional[Locator]:
        try:
            return self.page.locator("input[type='password']").first
        except Exception:
            return None

    def _submit(self) -> Optional[Locator]:
        rx = re.compile(r"login|log\s*in|sign\s*in", re.I)
        try:
            return self.page.get_by_role("button", name=rx).first
        except Exception:
            return None

    def login(self, username: str, password: str, wait_response_ms: int = 15000) -> ResponseLike:
        u = self._username()
        p = self._password()
        if u:
            try:
                u.fill("")
                u.fill(username)
            except Exception:
                pass
        if p:
            try:
                p.fill("")
                p.fill(password)
            except Exception:
                pass
        btn = self._submit()
        if btn:
            try:
                btn.click()
            except Exception:
                pass

        patt = re.compile(r"/(auth|login|session|token)", re.I)
        status = None
        url = self.page.url
        body = ""
        try:
            resp = self.page.wait_for_response(lambda r: patt.search(r.url or "") is not None, timeout=wait_response_ms)
            status = resp.status if hasattr(resp, "status") else None
            url = getattr(resp, "url", url)
            try:
                body = resp.text() or ""
            except Exception:
                body = ""
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        return ResponseLike(status=status, url=url, body=body)
