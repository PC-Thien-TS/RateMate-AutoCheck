# pages/login_page.py
import re
from playwright.sync_api import Page, TimeoutError as PWTimeout

_ERR = (
    '[data-test="login-error"],'
    '.ant-form-item-explain-error,'
    '.ant-message-error,'
    '.ant-message-notice-content,'
    '.ant-notification-notice-message,'
    '[role="alert"],'
    '.MuiAlert-root,'
    '.Toastify__toast--error'
)

def _click_email_tab_if_any(p: Page):
    # Một số site có tab "Email / Phone"
    try:
        tab = p.get_by_role("tab", name=re.compile(r"\bemail\b", re.I)).first
        if tab.is_visible():
            tab.click()
    except Exception:
        pass

def _first_visible(p: Page, locator, timeout=5000):
    l = locator.first
    l.wait_for(state="visible", timeout=timeout)
    return l

class LoginPage:
    def __init__(self, page: Page, base_url: str, login_path: str):
        self.page = page
        self.base_url = (base_url or "").rstrip("/")
        self.login_path = login_path or "/login"

    def goto(self):
        url = f"{self.base_url}{self.login_path}"
        self.page.goto(url, wait_until="domcontentloaded")

    def login(self, email: str, password: str):
        p = self.page
        _click_email_tab_if_any(p)

        # EMAIL
        email_loc = (
            p.get_by_label(re.compile(r"^(e-?mail|email address)$", re.I))
            .or_(p.get_by_placeholder(re.compile(r"email", re.I)))
            .or_(p.locator('input#email, input[name="email"], input[type="email"]'))
        )
        _first_visible(p, email_loc, timeout=10000).fill(email)

        # PASSWORD
        pw_loc = (
            p.get_by_label(re.compile(r"password", re.I))
            .or_(p.get_by_placeholder(re.compile(r"password", re.I)))
            .or_(p.locator('input[type="password"], input#password, input[name="password"]'))
        )
        _first_visible(p, pw_loc, timeout=10000).fill(password)

        # SUBMIT
        btn = (
            p.get_by_role("button", name=re.compile(r"(sign\s*in|log\s*in|đăng\s*nhập)", re.I))
            .or_(p.locator('button[type="submit"], [type="submit"]'))
        )
        _first_visible(p, btn, timeout=8000).click()
        p.wait_for_timeout(500)  # chống double submit nhanh

    def error_locator(self):
        return self.page.locator(_ERR)
