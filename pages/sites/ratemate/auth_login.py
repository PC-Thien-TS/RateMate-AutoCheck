# pages/sites/ratemate2/auth_login.py
from __future__ import annotations
import re, time
from typing import Optional
from playwright.sync_api import Page, Locator

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

class LoginPage:
    """Login modal có tab 'Phone number' / 'Email' và nút 'Sign in'."""

    def __init__(self, page: Page, base_url: str, path: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
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
        return self.page.get_by_role("button", name=re.compile(r"sign\s*in|login", re.I)).first

    # ---------- actions ----------
    def login(self, email: str, password: str) -> None:
        self._email().fill(email)
        self._password().fill(password)
        self._submit().click()
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
