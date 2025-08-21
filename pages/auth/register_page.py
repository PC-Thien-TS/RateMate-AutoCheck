import re
from playwright.sync_api import Page, TimeoutError as PWTimeout
from .login_page import LoginPage

REG_RE = re.compile(r"(Sign\s*up|Register|Create\s+an\s+account|Đăng\s*ký|注册)", re.I)

class RegisterPage:
    def __init__(self, page: Page, base_url: str, register_path: str = "/en/login"):
        self.page = page
        self.base_url = base_url
        self.login_path = register_path

    # ---------- navigation ----------
    def goto(self):
        lp = LoginPage(self.page, self.base_url, self.login_path)
        lp.goto()
        lp.open_register()  # dẫn tới /register

    # ---------- robust field getters (label -> placeholder -> id/data-test) ----------
    def _first_name(self):
        loc = self.page.get_by_label(re.compile(r"(First\s*name|Tên)", re.I))
        loc = loc.or_(self.page.get_by_placeholder(re.compile(r"^First name$", re.I)))
        loc = loc.or_(self.page.locator('#first_name,[data-test="first-name"]'))
        return loc.first

    def _last_name(self):
        loc = self.page.get_by_label(re.compile(r"(Last\s*name|Họ)", re.I))
        loc = loc.or_(self.page.get_by_placeholder(re.compile(r"^Last name$", re.I)))
        loc = loc.or_(self.page.locator('#last_name,[data-test="last-name"]'))
        return loc.first

    def _email(self):
        loc = self.page.get_by_label(re.compile(r"^Email", re.I))
        loc = loc.or_(self.page.get_by_placeholder(re.compile(r"^Email$", re.I)))
        loc = loc.or_(self.page.locator('#email,[data-test="email"]'))
        return loc.first

    def _password(self):
        loc = self.page.get_by_label(re.compile(r"^Password(?!.*Confirm)", re.I))
        loc = loc.or_(self.page.get_by_placeholder(re.compile(r"^Password$", re.I)))
        loc = loc.or_(self.page.locator('#password,[data-test="password"]'))
        return loc.first

    def _confirm(self):
        loc = self.page.get_by_label(re.compile(r"(Confirm\s*password|Re-?enter\s*password|Nhập\s*lại|确认密码)", re.I))
        loc = loc.or_(self.page.get_by_placeholder(re.compile(r"^Confirm password$", re.I)))
        loc = loc.or_(self.page.locator('#confirm_password,[data-test="confirm-password"]'))
        return loc.first

    def _submit_btn(self):
        loc = self.page.get_by_role("button", name=REG_RE)
        if loc.count() == 0:
            loc = self.page.locator(
                ':is(button[type="submit"], button:has-text("Register"), button:has-text("Sign up"), button:has-text("Đăng ký"), button:has-text("注册"))'
            )
        return loc.first

    # ---------- actions ----------
    def register_fill(self, email: str, password: str):
        self._first_name().fill("Test")
        self._last_name().fill("User")
        self._email().fill(email)
        self._password().fill(password)
        # confirm luôn luôn phải có trên form này
        self._confirm().fill(password)

    def submit(self):
        self._submit_btn().click()
        try:
            self.page.wait_for_load_state("networkidle", timeout=4000)
        except PWTimeout:
            pass

    def register_and_wait_response(self, email: str, password: str, timeout: int = 8000):
        """
        Điền đủ các trường và submit. Bắt POST liên quan register/auth; trả None nếu không có POST.
        """
        patterns = ("register", "signup", "sign-up", "sign_up", "auth", "login")
        def _match(resp):
            try:
                if resp.request.method != "POST":
                    return False
                url = resp.url.lower()
                return any(p in url for p in patterns)
            except Exception:
                return False

        try:
            with self.page.expect_response(_match, timeout=timeout) as resp_info:
                self.register_fill(email, password)
                self.submit()
            return resp_info.value
        except PWTimeout:
            return None

    def visible_error_locator(self):
        return self.page.locator(
            ':is([data-test="register-error"], .ant-form-item-explain-error, .ant-message-error, '
            '.ant-message-notice-content, .ant-notification-notice-message, [role="alert"], '
            '.MuiAlert-root, .Toastify__toast--error)'
        ).first
