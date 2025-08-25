# pages/register_page.py
import re
from typing import Optional
from playwright.sync_api import Page, Response, expect

_ERR_SEL = (
    ':is('
    '[data-test="register-error"],'
    '.ant-form-item-explain-error,'
    '.ant-message-error,'
    '.ant-message-notice-content,'
    '.ant-notification-notice-message,'
    '[role="alert"],'
    '.MuiAlert-root,'
    '.Toastify__toast--error'
    ')'
)

_SIGNUP_BTN = 'button:has-text("Sign up"), [type="submit"]:has-text("Sign up")'
_TAB_EMAIL = 'role=tab[name=/^email$/i]'
_TAB_PHONE = 'role=tab[name=/^phone( number)?$/i]'

class RegisterPage:
    def __init__(self, page: Page, base_url: str, register_path: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.register_path = register_path

    # ------- Helpers -------
    def visible_error_locator(self):
        # luôn dùng .first để tránh strict mode
        return self.page.locator(_ERR_SEL).first

    def _open_register_ui(self):
        url = f"{self.base_url}{self.register_path}"
        self.page.goto(url, wait_until="domcontentloaded")
        # Trường hợp vào /login và cần bấm “Sign up”
        signup_link = self.page.get_by_role("link", name=re.compile(r"sign up", re.I))
        if signup_link.count() > 0:
            signup_link.first.click()
        # Đảm bảo dialog/khối đăng ký hiện
        # (không fail nếu trang đã là form đăng ký)
        try:
            self.page.get_by_role("heading", name=re.compile(r"sign up", re.I)).wait_for(timeout=3000)
        except Exception:
            pass

    def _fill_common_passwords(self, password: str, confirm: Optional[str] = None):
        confirm = confirm if confirm is not None else password
        # điền password & confirm qua placeholder (bền với UI mới)
        self.page.get_by_placeholder(re.compile(r"password", re.I)).first.fill(password)
        self.page.get_by_placeholder(re.compile(r"confirm\s*password", re.I)).first.fill(confirm)

    # ------- Public APIs -------
    def goto(self):
        self._open_register_ui()

    def register_email(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        confirm_password: Optional[str] = None,
        wait_response_ms: int = 12000,
    ) -> Optional[Response]:
        """Đăng ký qua tab Email của form mới."""
        self._open_register_ui()

        # chuyển tab Email (nếu tồn tại)
        tab_email = self.page.locator(_TAB_EMAIL)
        if tab_email.count() > 0:
            tab_email.first.click()

        # điền các trường
        self.page.get_by_placeholder(re.compile(r"email", re.I)).first.fill(email)
        if full_name:
            self.page.get_by_placeholder(re.compile(r"full\s*name|name", re.I)).first.fill(full_name)
        self._fill_common_passwords(password, confirm_password)

        # submit
        with self.page.expect_response(lambda r: r.request.method in ("POST", "PUT", "PATCH") and re.search(r"signup|register|users", r.url, re.I), timeout=wait_response_ms) as resp:
            self.page.locator(_SIGNUP_BTN).first.click()
        try:
            return resp.value
        except Exception:
            return None

    def register_phone(
        self,
        phone_with_cc: str,
        password: str,
        full_name: Optional[str] = None,
        confirm_password: Optional[str] = None,
        wait_response_ms: int = 12000,
    ) -> Optional[Response]:
        """Đăng ký qua tab Phone number (nếu cần)."""
        self._open_register_ui()

        tab_phone = self.page.locator(_TAB_PHONE)
        if tab_phone.count() > 0:
            tab_phone.first.click()

        # country code thường là một dropdown; ở đây ưu tiên field "Phone number"
        self.page.get_by_placeholder(re.compile(r"phone\s*number|phone", re.I)).first.fill(phone_with_cc)
        if full_name:
            self.page.get_by_placeholder(re.compile(r"full\s*name|name", re.I)).first.fill(full_name)
        self._fill_common_passwords(password, confirm_password)

        with self.page.expect_response(lambda r: r.request.method in ("POST", "PUT", "PATCH") and re.search(r"signup|register|users", r.url, re.I), timeout=wait_response_ms) as resp:
            self.page.locator(_SIGNUP_BTN).first.click()
        try:
            return resp.value
        except Exception:
            return None
