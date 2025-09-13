# pages/factory.py
from importlib import import_module
from .auth.login_page import LoginPage as GenericLoginPage
from .auth.register_page import RegisterPage as GenericRegisterPage
import os
import re
import contextlib
import pytest
from pages.factory import PageFactory
from typing import Optional
from playwright.sync_api import TimeoutError, Error as PlaywrightError
from pages.sites.ratemate.auth_login import LoginResult, LoginPage
from dataclasses import dataclass
from typing import Optional, Dict, Any
import contextlib
from playwright.sync_api import Page, TimeoutError

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

class PageFactory:
    """
    Simple factory that holds Playwright page and opts.
    Provide methods that lazily import and return concrete Page objects to avoid circular imports.
    """

    def __init__(self, page, opts: Dict[str, Any]):
        self.page = page
        self.opts = opts

    def login(self):
        # lazy import để tránh circular imports
        from pages.sites.ratemate.auth_login import LoginPage
        return LoginPage(self.page, self.opts)

    def register(self):
        try:
            from pages.sites.ratemate.auth_register import RegisterPage
            return RegisterPage(self.page, self.opts)
        except Exception:
            return None

    # thêm accessor khác tương tự với lazy import

# Re-export generic pages for convenience imports
LoginPage = GenericLoginPage
RegisterPage = GenericRegisterPage

__all__ = ["PageFactory", "LoginPage", "RegisterPage"]

@dataclass
class LoginResult:
    status: Optional[int] = None
    final_url: Optional[str] = None
    error: Optional[str] = None
    body: Optional[str] = None

class LoginPage:
    """
    Lightweight LoginPage used by tests.
    Construct with: LoginPage(page, opts) where opts includes base_url and login_path.
    """

    def __init__(self, page: Page, opts: Dict[str, Any]):
        self.page = page
        self.base_url = opts.get("base_url", "") or ""
        self.login_path = opts.get("login_path", "/login") or "/login"

    def goto(self):
        url = self.base_url.rstrip("/") + "/" + self.login_path.lstrip("/")
        try:
            self.page.goto(url, timeout=15000)
        except Exception:
            # best-effort navigation; tests will assert on final state
            pass

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

