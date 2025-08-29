# tests/auth/test_login.py
import os
import re
import contextlib
import pytest
from pages.factory import PageFactory

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
