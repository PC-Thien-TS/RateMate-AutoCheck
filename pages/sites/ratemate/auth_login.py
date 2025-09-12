# pages/sites/ratemate/auth_login.py
from __future__ import annotations
import re, time
from typing import Optional
from playwright.sync_api import Page, Locator
from pages.core.base_page import BasePage

_ERR_RE = re.compile(r"(incorrect|not\s*valid|invalid|wrong|failed|error|required)", re.I)

def _union_error(scope):
    groups = [
        "[role='alert'], [aria-live='assertive']",
        ".error, .error-message, .text-danger, .text-red-500, .text-red-600",
        ".MuiFormHelperText-root, .form-helper-text, .help.is-danger",
        "p:has-text('Incorrect email or password')",
    ]
    loc = scope.locator("css=" + groups[0])
    for g in groups[1:]:
        loc = loc.or_(scope.locator("css=" + g))
    return loc

class LoginPage(BasePage):
    """Login modal có tab 'Phone number' / 'Email' và nút 'Sign in'."""

    def __init__(self, page: Page, base_url: str, path: str):
        super().__init__(page, base_url)
        self.path = path if path.startswith("/") else f"/{path}"

    # ---------- navigation ----------
    def goto(self):
        # mở trang và chờ modal hiện
        self.page.goto(f"{self.base_url}{self.path}", wait_until="domcontentloaded")
        # bảo đảm tab Email được chọn
        email_tab = self.page.get_by_role("tab", name=re.compile(r"email", re.I))
        if email_tab.count() > 0:
            email_tab.first.click()

    # ---------- locators ----------
    def _email(self) -> Locator:
        # input email trong modal
        return ( self.page.get_by_placeholder(re.compile(r"email", re.I))
                 .or_(self.page.get_by_role("textbox", name=re.compile(r"email", re.I)))
                 .first )

    def _password(self) -> Locator:
        return ( self.page.locator("input[type='password']")
                 .or_(self.page.get_by_placeholder(re.compile(r"password", re.I)))
                 .first )

    def _submit(self) -> Locator:
        # Be generous: role name, explicit submit types, and text fallbacks
        rx = re.compile(r"(login|log\s*in|sign\s*in|continue)", re.I)
        by_role = self.page.get_by_role("button", name=rx)
        css_submit = self.page.locator("button[type='submit'], input[type='submit']")
        css_named = self.page.locator(
            "button:has-text('Login'), button:has-text('Log in'), button:has-text('Sign in')"
        )
        links_named = self.page.get_by_role("link", name=rx)
        cand = by_role.or_(css_submit).or_(css_named).or_(links_named)
        # Avoid ion-searchbar reset buttons if present
        return cand.filter(has_not=self.page.locator("[aria-label='reset']")).locator(":not(ion-searchbar *)").first

    # ---------- actions ----------
    def login(self, email: str, password: str) -> None:
        self._email().fill(email)
        self._password().fill(password)
        btn = self._submit()
        try:
            btn.wait_for(state="visible", timeout=4_000)
            btn.click(timeout=3_000)
        except Exception:
            # Fallback: press Enter in password field
            try:
                self._password().press("Enter", timeout=800)
            except Exception:
                pass
        # đợi UI phản hồi nhẹ
        self.page.wait_for_timeout(300)

    # ---------- errors ----------
    def visible_error_text(self, timeout: int = 4000) -> str:
        end = time.time() + timeout/1000
        loc = _union_error(self.page)
        txt = ""
        while time.time() < end:
            try:
                if loc.count() and loc.first.is_visible():
                    t = (loc.first.inner_text(timeout=300) or "").strip()
                    if t:
                        txt = t
                        break
            except Exception:
                pass
            self.page.wait_for_timeout(150)
        return txt

    def has_error(self) -> tuple[bool, str]:
        t = self.visible_error_text(4000)
        return bool(_ERR_RE.search(t)), t
# pages/sites/ratemate/auth_login.py
from __future__ import annotations
import re
import time
from typing import Optional

from playwright.sync_api import Page, Locator
from pages.core.base_page import BasePage

_ERR_RE = re.compile(r"(incorrect|not\s*valid|invalid|wrong|failed|error|required)", re.I)


def _union_error(scope):
    groups = [
        "[role='alert'], [aria-live='assertive']",
        ".error, .error-message, .text-danger, .text-red-500, .text-red-600",
        ".MuiFormHelperText-root, .form-helper-text, .help.is-danger",
        "p:has-text('Incorrect email or password')",
    ]
    loc = scope.locator("css=" + groups[0])
    for g in groups[1:]:
        loc = loc.or_(scope.locator("css=" + g))
    return loc


class LoginPage(BasePage):
    """Login page for ratemate store (email/password + Log in button)."""

    def __init__(self, page: Page, base_url: str, path: str):
        super().__init__(page, base_url)
        self.path = path if path.startswith("/") else f"/{path}"

    # ---------- navigation ----------
    def goto(self):
        self.page.goto(f"{self.base_url}{self.path}", wait_until="domcontentloaded")

    # ---------- locators ----------
    def _email(self) -> Locator:
        return (
            self.page.get_by_placeholder(re.compile(r"email", re.I))
            .or_(self.page.get_by_role("textbox", name=re.compile(r"email", re.I)))
        ).first

    def _password(self) -> Locator:
        return (
            self.page.locator("input[type='password']")
            .or_(self.page.get_by_placeholder(re.compile(r"password", re.I)))
        ).first

    def _submit(self) -> Locator:
        # Support "Log in", "Login", and "Sign in"
        return self.page.get_by_role(
            "button", name=re.compile(r"(log\s*in|login|sign\s*in)", re.I)
        ).first

    # ---------- actions ----------
    def login(self, email: str, password: str) -> None:
        self._email().fill(email)
        self._password().fill(password)
        btn = self._submit()
        try:
            btn.wait_for(state="visible", timeout=10_000)
        except Exception:
            pass
        btn.click(timeout=30_000)
        self.page.wait_for_timeout(300)

    # ---------- errors ----------
    def visible_error_text(self, timeout: int = 4000) -> str:
        end = time.time() + timeout / 1000
        loc = _union_error(self.page)
        txt = ""
        while time.time() < end:
            try:
                if loc.count() and loc.first.is_visible():
                    t = (loc.first.inner_text(timeout=300) or "").strip()
                    if t:
                        txt = t
                        break
            except Exception:
                pass
            self.page.wait_for_timeout(150)
        return txt

    def has_error(self) -> tuple[bool, str]:
        t = self.visible_error_text(4000)
        return bool(_ERR_RE.search(t)), t
# pages/sites/ratemate/auth_login.py
from __future__ import annotations
import re
import time
from typing import Optional

from playwright.sync_api import Page, Locator
from pages.core.base_page import BasePage

_ERR_RE = re.compile(r"(incorrect|not\s*valid|invalid|wrong|failed|error|required)", re.I)


def _union_error(scope):
    groups = [
        "[role='alert'], [aria-live='assertive']",
        ".error, .error-message, .text-danger, .text-red-500, .text-red-600",
        ".MuiFormHelperText-root, .form-helper-text, .help.is-danger",
        "p:has-text('Incorrect email or password')",
    ]
    loc = scope.locator("css=" + groups[0])
    for g in groups[1:]:
        loc = loc.or_(scope.locator("css=" + g))
    return loc


class LoginPage(BasePage):
    """Login page for ratemate store (email/password + Log in button)."""

    def __init__(self, page: Page, base_url: str, path: str):
        super().__init__(page, base_url)
        self.path = path if path.startswith("/") else f"/{path}"

    # ---------- navigation ----------
    def goto(self):
        self.page.goto(f"{self.base_url}{self.path}", wait_until="domcontentloaded")

    # ---------- locators ----------
    def _email(self) -> Locator:
        return (
            self.page.get_by_placeholder(re.compile(r"email", re.I))
            .or_(self.page.get_by_role("textbox", name=re.compile(r"email", re.I)))
        ).first

    def _password(self) -> Locator:
        return (
            self.page.locator("input[type='password']")
            .or_(self.page.get_by_placeholder(re.compile(r"password", re.I)))
        ).first

    def _submit(self) -> Locator:
        # Support "Log in", "Login", and "Sign in"; fallback to submit button
        by_role = self.page.get_by_role(
            "button", name=re.compile(r"(log\s*in|login|sign\s*in)", re.I)
        )
        return by_role.or_(self.page.locator("button[type='submit']")).first

    # ---------- actions ----------
    def login(self, email: str, password: str) -> None:
        self._email().fill(email)
        self._password().fill(password)
        btn = self._submit()
        try:
            btn.wait_for(state="visible", timeout=10_000)
        except Exception:
            pass
        btn.click(timeout=30_000)
        self.page.wait_for_timeout(300)

    # ---------- errors ----------
    def visible_error_text(self, timeout: int = 4000) -> str:
        end = time.time() + timeout / 1000
        loc = _union_error(self.page)
        txt = ""
        while time.time() < end:
            try:
                if loc.count() and loc.first.is_visible():
                    t = (loc.first.inner_text(timeout=300) or "").strip()
                    if t:
                        txt = t
                        break
            except Exception:
                pass
            self.page.wait_for_timeout(150)
        return txt

    def has_error(self) -> tuple[bool, str]:
        t = self.visible_error_text(4000)
        return bool(_ERR_RE.search(t)), t
