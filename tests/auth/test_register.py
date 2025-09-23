# tests/auth/test_register.py
import os, re, pytest, contextlib, time
from pages.factory import PageFactory

_ERR_RE_DUP = re.compile(r"(exist|already|duplicate|taken|registered|trùng|đã\s*tồn|invalid|error)", re.I)
_ERR_RE_PW  = re.compile(r"(password|mật\s*khẩu|invalid|incorrect|sai|không\s*hợp\s*lệ|error)", re.I)

def _factory(new_page, site, base_url, auth_paths):
    return PageFactory(new_page, {
        "site": site,
        "base_url": base_url,
        "login_path": auth_paths["login"],
        "register_path": auth_paths["register"],
    })

def _visible_error_text(page, picker):
    with contextlib.suppress(Exception):
        t = picker(timeout=5000)  # reg.visible_error_text(...)
        return t or ""
    return ""

def _fallback_still_on_register_or_signin(page, auth_paths):
    url = page.url
    return url.endswith(auth_paths["register"]) or re.search(r"sign[-_]?up|sign[-_]?in|register", url, re.I)

@pytest.mark.auth
def test_register_duplicate_email_returns_error(new_page, site, base_url, auth_paths, credentials):
    reg = _factory(new_page, site, base_url, auth_paths).register()
    reg.goto()
    full_name = os.getenv("FULL_NAME") or "QA Auto"
    resp = reg.register_email(credentials["email"], credentials["password"], full_name, wait_response_ms=15000)

    # 1) HTTP status coi như báo lỗi hợp lệ
    if getattr(resp, "status", None) in {400,401,403,409,422}:
        return

    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(300)

    # 2) UI text
    msg = _visible_error_text(new_page, reg.visible_error_text)
    if _ERR_RE_DUP.search(msg or ""):
        return

    # 3) Fallback: vẫn ở trang register / chuyển về sign-in
    assert _fallback_still_on_register_or_signin(new_page, auth_paths), f"Expected duplicate/error (status/UI/url), got msg='{msg}'"

@pytest.mark.auth
def test_register_existing_email_wrong_password_shows_error(new_page, site, base_url, auth_paths, credentials):
    reg = _factory(new_page, site, base_url, auth_paths).register()
    reg.goto()
    wrong_pw = (credentials["password"] or "P@ssw0rd!") + "_WRONG!"
    full_name = os.getenv("FULL_NAME") or "QA Auto"
    resp = reg.register_email(credentials["email"], wrong_pw, full_name, wait_response_ms=15000)

    if getattr(resp, "status", None) in {400,401,403,409,422}:
        return

    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(300)

    msg = _visible_error_text(new_page, reg.visible_error_text)
    if _ERR_RE_PW.search(msg or ""):
        return

    assert _fallback_still_on_register_or_signin(new_page, auth_paths), f"Expected password error (status/UI/url); got msg='{msg}'"


@pytest.mark.auth
@pytest.mark.write
@pytest.mark.skipif(os.getenv("E2E_ALLOW_WRITE") != "1", reason="E2E_ALLOW_WRITE is not 1")
@pytest.mark.tc(id="RM-REG-003", title="Register new user successfully", area="Auth", severity="High")
def test_register_success(new_page, site, base_url, auth_paths):
    reg = _factory(new_page, site, base_url, auth_paths).register()
    reg.goto()

    # Generate a unique email and a secure password
    timestamp = int(time.time())
    new_email = f"testuser.{timestamp}@example.com"
    new_password = f"SecureP@ssw0rd_{timestamp}!"
    full_name = "Test User"

    resp = reg.register_email(new_email, new_password, full_name, wait_response_ms=15000)

    # Expect a successful status code (e.g., 200, 201) or a redirect (3xx)
    assert resp and resp.status in {200, 201, 302, 303, 307}, f"Registration failed with status {getattr(resp, 'status', 'N/A')}"

    # After successful registration, user might be redirected to login or dashboard
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("networkidle", timeout=5000)

    final_url = new_page.url
    on_login_page = auth_paths["login"] in final_url
    on_dashboard = "dashboard" in final_url or "profile" in final_url

    assert on_login_page or on_dashboard, \
        f"Expected to be on login or dashboard page after registration, but was on {final_url}"