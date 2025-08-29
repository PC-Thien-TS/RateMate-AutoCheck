# pages/auth/register_page.py
from __future__ import annotations
import re, time, contextlib
from typing import Optional
from playwright.sync_api import Page, Locator

class ResponseLike:
    def __init__(self, status=None, url="", body=""):
        self.status = status
        self.url = url
        self._body = body
    def text(self): return self._body or ""

def _pick_visible(raw: Locator, timeout_ms: int = 8000) -> Locator:
    end = time.time() + timeout_ms/1000
    while time.time() < end:
        with contextlib.suppress(Exception):
            n = raw.count()
            for i in range(min(n, 10)):
                el = raw.nth(i)
                if el.is_visible():
                    return el
        raw.page.wait_for_timeout(120)
    return raw.first

def _input_union(scope, patterns: str) -> Locator:
    rx = re.compile(patterns, re.IGNORECASE)
    return scope.get_by_label(rx).or_(
        scope.get_by_placeholder(rx)
    ).or_(
        scope.get_by_role("textbox", name=rx)
    ).or_(
        scope.locator("input, textarea, [contenteditable], [contenteditable='true']")
    )

class RegisterPage:
    def __init__(self, page: Page, base_url: str, path: str):
        self.page = page
        self.base_url = (base_url or "").rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"

    def goto(self):
        self.page.goto(f"{self.base_url}{self.path}", wait_until="domcontentloaded")

    def _open_register_ui(self):
        with contextlib.suppress(Exception):
            tab = self.page.get_by_role("tab", name=re.compile(r"(register|sign\s*up)", re.I))
            if tab.count() > 0:
                tab.first.click()

    def _fill_email(self, email: str):
        el = _pick_visible(_input_union(self.page, r"(e-?mail|email)"))
        with contextlib.suppress(Exception): el.fill("")
        el.fill(email)

    def _fill_full_name(self, name: str):
        el = _pick_visible(_input_union(self.page, r"(full\s*name|name|họ|tên)"))
        with contextlib.suppress(Exception): el.fill("")
        with contextlib.suppress(Exception): el.fill(name)

    def _fill_password(self, pw: str):
        el = _pick_visible(_input_union(self.page, r"(password|mật\s*khẩu)"))
        with contextlib.suppress(Exception): el.fill("")
        el.fill(pw)

    def _fill_confirm(self, pw: str):
        el = _pick_visible(_input_union(self.page, r"(confirm|nhập\s*lại|re-?type|verify)"))
        with contextlib.suppress(Exception): el.fill("")
        with contextlib.suppress(Exception): el.fill(pw)

    def _click_submit(self):
        btn = _pick_visible(
            self.page.get_by_role("button", name=re.compile(r"(sign\s*up|register|create\s*account|submit)", re.I))
            .or_(self.page.locator("button[type='submit'], input[type='submit']"))
        )
        with contextlib.suppress(Exception):
            btn.click(timeout=3000)

    def visible_error_text(self, timeout: int = 5000) -> str:
        end = time.time() + timeout/1000
        # mở rộng selector: alert/status/message phổ biến
        loc = self.page.locator(
            "[role='alert'], [role='status'], "
            ".ant-form-item-explain-error, .ant-message-error, .ant-message-notice .ant-message-custom-content, "
            ".ant-notification-notice-message, .ant-notification-notice-description, "
            ".MuiAlert-root, .Toastify__toast--error, "
            ".error, .error-message, .text-danger, .invalid-feedback, "
            ".el-message__content, .v-alert__content, .toast-message, .notification-message"
        )
        while time.time() < end:
            with contextlib.suppress(Exception):
                if loc.count() > 0 and loc.first.is_visible():
                    t = (loc.first.inner_text(timeout=300) or "").strip()
                    if t:
                        return t
            self.page.wait_for_timeout(120)
        return ""

    def register_email(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        confirm_password: Optional[str] = None,
        wait_response_ms: int = 12000,
    ) -> ResponseLike:
        self._open_register_ui()
        if full_name:
            self._fill_full_name(full_name)
        self._fill_email(email)
        self._fill_password(password)
        self._fill_confirm(confirm_password or password)

        # chờ response POST/PUT/PATCH tới endpoint liên quan register
        patt = re.compile(r"(signup|sign[-_]?up|register|users|auth)", re.I)
        status=None; url=self.page.url; body=""
        with contextlib.suppress(Exception):
            with self.page.expect_response(
                lambda r: r.request and r.request.method in ("POST","PUT","PATCH") and patt.search(r.url or ""),
                timeout=wait_response_ms
            ) as resp:
                self._click_submit()
            r = resp.value
            with contextlib.suppress(Exception): status = r.status if hasattr(r, "status") else r.status()
            with contextlib.suppress(Exception): url = r.url
            with contextlib.suppress(Exception): body = r.text() or ""

        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)

        return ResponseLike(status=status, url=url, body=body)
