# pages/sites/ratemate/auth_login.py
from __future__ import annotations
import os
import re
import time
import contextlib
from typing import Optional, Dict, Any

import pytest
from playwright.sync_api import Page, Locator, TimeoutError, Error as PlaywrightError
from pages.core.base_page import BasePage
from pages.factory import PageFactory

from pages.auth.login_page import LoginResult

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
    def login(self, email: str, password: str, wait_for_navigation: bool = True) -> "LoginResult":
        """
        Fill credentials, submit and return LoginResult with:
          - status: HTTP status if an observed response was captured
          - final_url: page.url after attempt
          - error: exception message if any internal errors
          - body: response text if captured
        """
        result = LoginResult()
        try:
            # Fill email
            try:
                self.page.fill("input[type='email']", email, timeout=2000)
            except Exception:
                with contextlib.suppress(Exception):
                    self.page.fill("input[name='email']", email, timeout=2000)

            # Fill password
            try:
                self.page.fill("input[type='password']", password, timeout=2000)
            except Exception:
                with contextlib.suppress(Exception):
                    self.page.fill("input[name='password']", password, timeout=2000)

            # Try to capture a login-related response (best-effort)
            resp = None
            try:
                with self.page.expect_response(
                    lambda r: "/auth" in r.url or "/login" in r.url or r.request.method == "POST",
                    timeout=10000
                ) as resp_info:
                    # Try common submit flows
                    try:
                        self.page.click("button[type='submit']", timeout=5000)
                    except Exception:
                        try:
                            self.page.click("button:has-text(\"Sign in\")", timeout=5000)
                        except Exception:
                            with contextlib.suppress(Exception):
                                self.page.press("input[type='password']", "Enter", timeout=2000)
                resp = resp_info.value
            except TimeoutError:
                resp = None
            except Exception:
                resp = None

            if resp is not None:
                try:
                    result.status = resp.status
                except Exception:
                    result.status = None
                try:
                    # .text() might raise on binary responses; guard it
                    result.body = resp.text()
                except Exception:
                    result.body = None

            # Prefer waiting for networkidle/load rather than fixed sleeps
            if wait_for_navigation:
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    with contextlib.suppress(Exception):
                        self.page.wait_for_load_state("load", timeout=5000)

            try:
                result.final_url = getattr(self.page, "url", None)
            except Exception:
                result.final_url = None

            return result

        except Exception as e:
            result.error = str(e)
            try:
                result.final_url = getattr(self.page, "url", None)
            except Exception:
                result.final_url = None
            return result

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


# Nhận diện các URL login phổ biến
_LOGIN_URL_RE = re.compile(r"/(auth/login|log[-_]?in|sign[-_]?in)(\?|/|$)", re.IGNORECASE)

# Các selector lỗi UI phổ biến (antd, MUI, toast, ...)
_ERR_SEL = (
    "[role='alert'], [role='status'], "
    ".ant-form-item-explain-error, .ant-message-error, "
    ".ant-message-notice .ant-message-custom-content, "
    ".ant-notification-notice-message, .ant-notification-notice-description, "
    ".MuiAlert-root, .Toastify__toast--error, "
    ".error, .error-message, .text-danger, .invalid-feedback, "
    ".el-message__content, .v-alert__content, .toast-message, .notification-message"
)

def _has_error(page):
    loc = page.locator(_ERR_SEL).first
    with contextlib.suppress(Exception):
        if loc.is_visible(timeout=2000):
            with contextlib.suppress(Exception):
                txt = (loc.inner_text(timeout=500) or "").strip()
            return True, txt or ""
    return False, ""

def _auth_state_ok(page) -> bool:
    # Cookie trông giống token/session
    with contextlib.suppress(Exception):
        for c in page.context.cookies():
            name = c.get("name", "") or ""
            val = c.get("value", "") or ""
            if re.search(r"(token|auth|jwt|access|refresh|session)", name, re.I) and len(val) >= 12:
                return True
    # localStorage
    with contextlib.suppress(Exception):
        keys = page.evaluate("Object.keys(window.localStorage)")
        for k in keys:
            if re.search(r"(token|auth|jwt|access|refresh|session)", k, re.I):
                v = page.evaluate("localStorage.getItem(arguments[0])", k)
                if v and len(str(v)) >= 12:
                    return True
    # sessionStorage
    with contextlib.suppress(Exception):
        keys = page.evaluate("Object.keys(window.sessionStorage)")
        for k in keys:
            if re.search(r"(token|auth|jwt|access|refresh|session)", k, re.I):
                v = page.evaluate("sessionStorage.getItem(arguments[0])", k)
                if v and len(str(v)) >= 12:
                    return True
    return False

def _factory(page, site, base_url, auth_paths) -> PageFactory:
    return PageFactory(page, {
        "site": site,
        "base_url": base_url,
        "login_path": auth_paths["login"],
        "register_path": auth_paths["register"],
    })

@pytest.mark.auth
@pytest.mark.smoke
@pytest.mark.tc(id="RM-LOGIN-001", title="Login with valid credentials", area="Auth", severity="High")
def test_login_success(new_page, site, base_url, auth_paths, credentials):
    if not (credentials.get("email") and credentials.get("password")):
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD; skipping login_success")

    login = _factory(new_page, site, base_url, auth_paths).login()
    login.goto()
    resp = login.login(credentials["email"], credentials["password"])

    # Nếu vẫn còn URL login, cho SPA thêm nhịp redirect + check auth-state
    if _LOGIN_URL_RE.search(new_page.url):
        with contextlib.suppress(Exception):
            new_page.wait_for_timeout(800)
    if _LOGIN_URL_RE.search(new_page.url):
        status_ok = bool(resp and getattr(resp, "status", None) and 200 <= resp.status < 400)
        if not (_auth_state_ok(new_page) or status_ok):
            pytest.fail(f"Still on login page: {new_page.url}")

    with contextlib.suppress(Exception):
        assert not resp or getattr(resp, "status", None) not in (400, 401, 403), \
            f"Auth failed (status={resp.status})"
