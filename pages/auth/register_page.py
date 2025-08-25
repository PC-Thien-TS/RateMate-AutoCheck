# pages/auth/register_page.py
import re
from typing import Optional
from playwright.sync_api import Page, Response

# ===== Vùng hiển thị lỗi phổ biến (AntD, MUI, Toastify, v.v.) =====
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

# ===== Regex text cho nút/link/tab =====
_BTN_TEXT_RE   = re.compile(r"(sign\s*up|register|create\s*account|đăng\s*ký|tạo\s*tài\s*khoản)", re.I)
_TAB_EMAIL_RE  = re.compile(r"^email$", re.I)
_TAB_PHONE_RE  = re.compile(r"^phone(\s*number)?$", re.I)

class RegisterPage:
    """POM Đăng ký – bền với thay đổi UI & ngôn ngữ (EN/VI)."""

    def __init__(self, page: Page, base_url: str, register_path: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.register_path = register_path

    # ---------- Helpers ----------
    def visible_error_locator(self):
        return self.page.locator(_ERR_SEL).first

    def _open_register_ui(self):
        """Đi đến màn hình đăng ký. Nếu đang ở /login thì bấm link/button 'Sign up/Đăng ký'."""
        url = f"{self.base_url}{self.register_path}"
        self.page.goto(url, wait_until="domcontentloaded")

        # TH1: có link chuyển sang đăng ký
        link = self.page.get_by_role("link", name=_BTN_TEXT_RE)
        if link.count() > 0:
            link.first.click()
        else:
            # TH2: có button chuyển
            btn = self.page.get_by_role("button", name=_BTN_TEXT_RE)
            if btn.count() > 0:
                btn.first.click()

        # Không fail nếu trang đã là form đăng ký
        try:
            self.page.get_by_role("heading", name=_BTN_TEXT_RE).first.wait_for(timeout=3000)
        except Exception:
            pass

    def _fill_email(self, email: str):
        # Ưu tiên placeholder/label, rồi fallback type=email
        cands = [
            self.page.get_by_placeholder(re.compile(r"email", re.I)).first,
            self.page.get_by_label(re.compile(r"email", re.I)).first,
            self.page.locator('input[type="email"]').first,
        ]
        for el in cands:
            if el.count() > 0:
                el.fill(email)
                return
        # Fallback cuối cùng: input bất kỳ có text/email kề cạnh
        self.page.locator("input").first.fill(email)

    def _fill_full_name(self, full_name: str):
        cands = [
            self.page.get_by_placeholder(re.compile(r"full\s*name|name", re.I)).first,
            self.page.get_by_label(re.compile(r"full\s*name|name", re.I)).first,
        ]
        for el in cands:
            if el.count() > 0:
                el.fill(full_name)
                return

    def _fill_common_passwords(self, password: str, confirm: Optional[str] = None):
        confirm = confirm if confirm is not None else password
        pw = [
            self.page.get_by_placeholder(re.compile(r"password", re.I)).first,
            self.page.get_by_label(re.compile(r"password", re.I)).first,
        ]
        cpw = [
            self.page.get_by_placeholder(re.compile(r"(confirm|repeat|retype).*(password)", re.I)).first,
            self.page.get_by_label(re.compile(r"(confirm|repeat|retype).*(password)", re.I)).first,
        ]
        for el in pw:
            if el.count() > 0:
                el.fill(password)
                break
        for el in cpw:
            if el.count() > 0:
                el.fill(confirm)
                break

    def _click_submit(self):
        # Ưu tiên role=button theo text; sau đó thử các biến thể
        btn = self.page.get_by_role("button", name=_BTN_TEXT_RE)
        if btn.count() > 0:
            btn.first.click()
            return
        for sel in ['button[type="submit"]', "button", '[role="button"]']:
            loc = self.page.locator(sel).filter(has_text=_BTN_TEXT_RE)
            if loc.count() > 0:
                loc.first.click()
                return
        # Fallback: submit form nếu có
        try:
            self.page.locator("form").first.evaluate("f => f.requestSubmit && f.requestSubmit()")
        except Exception:
            pass

    # ---------- Public APIs ----------
    def goto(self):
        self._open_register_ui()

    def register_email(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        confirm_password: Optional[str] = None,
        wait_response_ms: int = 15000,
    ) -> Optional[Response]:
        """Đăng ký bằng Email (mặc định form chung tại /en/login của RateMate)."""
        self._open_register_ui()

        # Chuyển tab Email nếu có
        tab_email = self.page.get_by_role("tab", name=_TAB_EMAIL_RE)
        if tab_email.count() > 0:
            tab_email.first.click()

        self._fill_email(email)
        if full_name:
            self._fill_full_name(full_name)
        self._fill_common_passwords(password, confirm_password)

        # Chờ response liên quan đến đăng ký
        with self.page.expect_response(
            lambda r: r.request.method in ("POST", "PUT", "PATCH")
            and re.search(r"(signup|register|users)", r.url, re.I),
            timeout=wait_response_ms,
        ) as resp:
            self._click_submit()
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
        wait_response_ms: int = 15000,
    ) -> Optional[Response]:
        """Đăng ký qua Phone number (nếu UI hỗ trợ tab Phone)."""
        self._open_register_ui()

        tab_phone = self.page.get_by_role("tab", name=_TAB_PHONE_RE)
        if tab_phone.count() > 0:
            tab_phone.first.click()

        phone_input = self.page.get_by_placeholder(re.compile(r"phone\s*number|phone", re.I)).first
        if phone_input.count() == 0:
            phone_input = self.page.get_by_label(re.compile(r"phone", re.I)).first
        if phone_input.count() > 0:
            phone_input.fill(phone_with_cc)

        if full_name:
            self._fill_full_name(full_name)
        self._fill_common_passwords(password, confirm_password)

        with self.page.expect_response(
            lambda r: r.request.method in ("POST", "PUT", "PATCH")
            and re.search(r"(signup|register|users)", r.url, re.I),
            timeout=wait_response_ms,
        ) as resp:
            self._click_submit()
        try:
            return resp.value
        except Exception:
            return None
