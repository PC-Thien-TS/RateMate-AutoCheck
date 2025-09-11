from __future__ import annotations
import re
import time
from typing import Optional

from playwright.sync_api import Page, Locator
from pages.core.base_page import BasePage
from pages.common_helpers import fill_force


class LoginPage(BasePage):
    """Login modal with tabs 'Phone number' / 'Email' and a 'Sign in' button (ratemate_app2).

    Heuristic behavior similar to ratemate variant: ensure Email tab is active,
    fill email/password, click Sign in.
    """

    def __init__(self, page: Page, base_url: str, path: str):
        super().__init__(page, base_url)
        self.path = path if path.startswith("/") else f"/{path}"

    # ---------- navigation ----------
    def goto(self):
        self.goto_path(self.path, wait_until="domcontentloaded")
        # try ensure Email tab
        try:
            email_tab = self.page.get_by_role("tab", name=re.compile(r"email", re.I))
            if email_tab.count() > 0:
                email_tab.first.click()
                self.wait_briefly(150)
        except Exception:
            pass
        # try open login modal from page header if present
        try:
            # Prefer ionic button with "Sign in" or Vietnamese equivalent
            ion = self.page.locator("ion-button:has-text('Sign in')").or_(
                self.page.locator("ion-button:has-text('Đăng nhập')")
            )
            if ion.count() > 0:
                ion.first.click()
                self.wait_briefly(400)
            else:
                rx_login = re.compile(r"(đăng\s*nhập|log\s*in|sign\s*in)", re.I)
                cand = self.page.get_by_text(rx_login)
                if cand.count() > 0:
                    cand.first.click()
                    self.wait_briefly(300)
        except Exception:
            pass
        try:
            link = self.page.locator("a[href*='login' i]")
            if link.count() > 0 and link.first.is_visible(timeout=800):
                link.first.click()
                self.wait_briefly(300)
        except Exception:
            pass

    # ---------- locators ----------
    def _email(self) -> Locator:
        # Prefer ionic inner input, then fall back
        return (
            self.page.locator("ion-input input[type='email']")
            .or_(self.page.locator("ion-input input[type='text']"))
            .or_(self.page.locator("input[type='email']"))
            .or_(self.page.locator("input[type='text']"))
        ).first

    def _password(self) -> Locator:
        return (
            self.page.locator("ion-input input[type='password']")
            .or_(self.page.locator("input[type='password']"))
        ).first

    def _submit(self) -> Locator:
        return self.page.get_by_role("button", name=re.compile(r"sign\s*in|login|log\s*in|continue", re.I)).first

    # ---------- actions ----------
    def login(self, email: str, password: str) -> None:
        # Ensure auth panel open (click Sign in if present)
        try:
            ion = self.page.locator("ion-button:has-text('Sign in')").or_(
                self.page.locator("ion-button:has-text('Đăng nhập')")
            )
            if ion.count() > 0 and ion.first.is_enabled():
                ion.first.click()
                self.wait_briefly(400)
        except Exception:
            pass
        # ensure auth modal/content visible
        try:
            self.page.locator("ion-input input").first.wait_for(state="visible", timeout=5_000)
        except Exception:
            self.wait_briefly(500)
        try:
            e = self._email()
            fill_force(e, email)
        except Exception:
            # Fallback: iterate visible inputs to find a non-search non-password field
            try:
                c = self.page.locator("input")
                n = min(c.count(), 20)
            except Exception:
                n = 0
            e = None
            for i in range(n):
                it = self.page.locator("input").nth(i)
                try:
                    if not it.is_visible(timeout=500):
                        continue
                    t = (it.get_attribute("type") or "").lower()
                    if t in ("password", "search", "button", "submit"):
                        continue
                    e = it
                    break
                except Exception:
                    continue
            if e is None:
                raise
            fill_force(e, email)
        # If password field is not visible yet, try to proceed to password step
        try:
            p = self._password()
        except Exception:
            p = None
        try:
            if not p.is_visible(timeout=800):
                nxt = self.page.get_by_role("button", name=re.compile(r"continue|next|ti\s*\p", re.I)).first
                if nxt and nxt.is_enabled():
                    nxt.click()
                    self.wait_briefly(200)
                try:
                    p = self._password()
                except Exception:
                    p = None
        except Exception:
            pass
        if p is None:
            # Fallback: visible password input in DOM
            try:
                p = self.page.locator("input[type='password']").first
                p.wait_for(state="visible", timeout=3_000)
            except Exception:
                pass
        if p:
            fill_force(p, password)
        self._submit().click()
        self.wait_briefly(300)
