import re
from playwright.sync_api import Page, TimeoutError as PWTimeout

LANG_NAME = {"en": "English", "vi": "Tiếng Việt", "zh": "中文"}
BTN_LOGIN_RE = re.compile(r"^(Log\s*in|Đăng\s*nhập|登录)$", re.I)

class LoginPage:
    def __init__(self, page: Page, base_url: str, login_path: str = "/en/login"):
        self.page = page
        self.url = f"{base_url}{login_path}"

    # ---- navigation ----
    def goto(self):
        self.page.goto(self.url, wait_until="domcontentloaded")
        self.dismiss_google_one_tap()

    # ---- helpers ----
    def _email(self):
        return self.page.get_by_label(re.compile(r"^Email", re.I)).or_(self.page.locator("#email")).first

    def _password(self):
        return self.page.get_by_label(re.compile(r"^Password", re.I)).or_(self.page.locator("#password")).first

    def _submit(self):
        # nút Log in (đa ngôn ngữ)
        loc = self.page.get_by_role("button", name=BTN_LOGIN_RE)
        if loc.count() == 0:
            loc = self.page.locator(
                ':is(button[type="submit"], button:has-text("Log in"), button:has-text("Đăng nhập"), button:has-text("登录"))'
            )
        return loc.first

    def dismiss_google_one_tap(self):
        # nếu One Tap hiện, ấn Esc để đóng (an toàn cả khi không có)
        try:
            self.page.keyboard.press("Escape")
        except Exception:
            pass

    # ---- actions ----
    def set_language(self, locale: str = "en"):
        name = LANG_NAME.get(locale, "English")
        # mở dropdown language ở góc phải
        toggler = self.page.get_by_role("button", name=re.compile("English|Tiếng Việt|中文"))
        if toggler.count() == 0:
            toggler = self.page.locator('button:has-text("English"), button:has-text("Tiếng Việt"), button:has-text("中文")')
        if toggler.count() > 0:
            toggler.first.click()
            self.page.get_by_text(name, exact=True).first.click()
            self.page.wait_for_load_state("networkidle")

    def open_register(self):
        # link "Create an account" / "Đăng ký" / "注册"
        link = self.page.get_by_role("link", name=re.compile(r"(Create an account|Đăng\s*ký|注册)", re.I))
        if link.count() == 0:
            link = self.page.locator(':is(a:has-text("Create an account"), a:has-text("Đăng ký"), a:has-text("注册"))')
        link.first.click()
        self.page.wait_for_load_state("networkidle")

    def login(self, email: str, password: str):
        self._email().fill(email)
        self._password().fill(password)
        self._submit().click()
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except PWTimeout:
            pass
