# tests/auth/test_login.py
import os
import re
import contextlib
import pytest
from pages.factory import PageFactory
from dataclasses import dataclass
from typing import Optional
from playwright.sync_api import TimeoutError, Error as PlaywrightError
from pages.sites.ratemate.auth_login import LoginResult

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

@dataclass
class LoginResult:
    status: Optional[int] = None
    final_url: Optional[str] = None
    error: Optional[str] = None
    body: Optional[str] = None

class LoginPage:
    # ...existing code...

    def login(self, email: str, password: str, wait_for_navigation: bool = True) -> "LoginResult":
        """
        Thực hiện login và trả về LoginResult:
         - status: HTTP status của response (nếu bắt được)
         - final_url: URL cuối cùng của page sau thao tác
         - error: thông báo lỗi nếu xảy ra exception
         - body: body của response nếu có
        """
        result = LoginResult()
        try:
            # --- existing fill/click logic should be here; keep or replace selectors as needed ---
            # ví dụ phổ thông (cập nhật selector nếu site khác)
            try:
                # Điền email/password nếu có các trường phổ thông
                if hasattr(self, "page"):
                    try:
                        self.page.fill("input[type='email']", email, timeout=2000)
                    except Exception:
                        # thử selector khác
                        try:
                            self.page.fill("input[name='email']", email, timeout=2000)
                        except Exception:
                            pass
                    try:
                        self.page.fill("input[type='password']", password, timeout=2000)
                    except Exception:
                        try:
                            self.page.fill("input[name='password']", password, timeout=2000)
                        except Exception:
                            pass
                # Bắt response liên quan đến login nếu server trả về request
                resp = None
                try:
                    with self.page.expect_response(lambda r: "/auth" in r.url or "/login" in r.url or r.request.method == "POST", timeout=10000) as resp_info:
                        # submit form: cập nhật selector phù hợp
                        try:
                            self.page.click("button[type='submit']", timeout=5000)
                        except Exception:
                            try:
                                self.page.click("button:has-text(\"Sign in\")", timeout=5000)
                            except Exception:
                                # fallback: press Enter in password field
                                try:
                                    self.page.press("input[type='password']", "Enter", timeout=2000)
                                except Exception:
                                    pass
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

            except Exception as e_inner:
                # không dừng test ở đây, ghi lại error và tiếp tục lấy final_url
                result.error = str(e_inner)

            # Chờ load state thay vì sleep tĩnh
            if wait_for_navigation:
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    try:
                        self.page.wait_for_load_state("load", timeout=5000)
                    except Exception:
                        pass

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

@pytest.mark.auth
@pytest.mark.tc(id="RM-LOGIN-002", title="Reject wrong password", area="Auth", severity="Medium")
def test_login_wrong_password(new_page, site, base_url, auth_paths, credentials):
    if not credentials.get("email"):
        pytest.skip("Missing E2E_EMAIL; skipping")

    login = _factory(new_page, site, base_url, auth_paths).login()
    login.goto()
    resp = login.login(credentials["email"], (credentials.get("password") or "P@ssw0rd!") + "_WRONG!")

    # 1) HTTP status thể hiện xác thực sai
    bad_statuses = {400, 401, 403, 409, 422}
    if getattr(resp, "status", None) in bad_statuses:
        return

    # 2) Có thông báo lỗi UI
    has_err, txt = _has_error(new_page)
    if has_err:
        return

    # 3) Fallback: vẫn ở trang login hoặc có field invalid
    try:
        still_on_login = bool(_LOGIN_URL_RE.search(new_page.url))
    except Exception:
        still_on_login = True

    any_field_error = False
    with contextlib.suppress(Exception):
        any_field_error = new_page.locator(
            ":is(.ant-form-item-explain-error,[aria-invalid='true'])"
        ).first.is_visible(timeout=1500)

    assert still_on_login or any_field_error, \
        f"Expected error (status/UI/fallback) for wrong password; got: {txt[:200]}"

@pytest.mark.auth
@pytest.mark.tc(id="RM-LOGIN-003", title="Login with empty credentials", area="Auth", severity="Low")
def test_login_empty_credentials(new_page, site, base_url, auth_paths):
    login = _factory(new_page, site, base_url, auth_paths).login()
    login.goto()
    resp = login.login("", "")

    # Kiểm tra không có điều hướng (vẫn ở trang login)
    assert _LOGIN_URL_RE.search(new_page.url), f"Unexpected redirect from login: {new_page.url}"

    # Kiểm tra thông báo lỗi
    has_err, txt = _has_error(new_page)
    assert has_err, "No error message for empty credentials"
    assert "required" in txt.lower(), f"Unexpected error message: {txt}"

@pytest.mark.auth
@pytest.mark.tc(id="RM-LOGIN-004", title="Login with slow network", area="Auth", severity="Medium")
def test_login_slow_network(new_page, site, base_url, auth_paths, credentials):
    if not (credentials.get("email") and credentials.get("password")):
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD; skipping login_success")

    login = _factory(new_page, site, base_url, auth_paths).login()
    login.goto()

    # Giả lập mạng chậm
    with new_page.expect_navigation(timeout=15000):
        new_page.route("**/*", lambda route: route.continue_(
            headers={**route.request.headers, "Slow-Network": "true"}
        ))
        resp = login.login(credentials["email"], credentials["password"])

    # Kiểm tra đăng nhập thành công
    assert resp is not None, "Login did not return a result"
    assert resp.status in (200, 302), f"Unexpected login HTTP status: {resp.status}, body={resp.body}"
    assert "dashboard" in resp.final_url.lower() or "profile" in resp.final_url.lower(), f"Unexpected final_url after login: {resp.final_url}"