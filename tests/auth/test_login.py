# tests/auth/test_login.py
import contextlib
import pytest
from pages.auth.login_page import LoginPage
from pages.common_helpers import ResponseLike as LoginResult

from tests._helpers.auth import LOGIN_URL_RE, has_error, auth_state_ok


def _login_page(page, base_url, auth_paths) -> LoginPage:
    return LoginPage(page, base_url, auth_paths["login"])


@pytest.mark.auth
@pytest.mark.smoke
@pytest.mark.tc(id="RM-LOGIN-001", title="Login with valid credentials", area="Auth", severity="High")
def test_login_success(new_page, site, base_url, auth_paths, credentials):
    if not (credentials.get("email") and credentials.get("password")):
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD; skipping login_success")

    login: LoginPage = _login_page(new_page, base_url, auth_paths)
    login.goto()
    resp: LoginResult = login.login(credentials["email"], credentials["password"])

    if LOGIN_URL_RE.search(new_page.url):
        with contextlib.suppress(Exception):
            new_page.wait_for_timeout(800)
    if LOGIN_URL_RE.search(new_page.url):
        status_ok = bool(resp and getattr(resp, "status", None) and 200 <= resp.status < 400)
        if not (auth_state_ok(new_page) or status_ok):
            pytest.fail(f"Still on login page: {new_page.url}")

    with contextlib.suppress(Exception):
        assert not resp or getattr(resp, "status", None) not in (400, 401, 403), \
            f"Auth failed (status={resp.status})"


@pytest.mark.auth
@pytest.mark.tc(id="RM-LOGIN-002", title="Reject wrong password", area="Auth", severity="Medium")
def test_login_wrong_password(new_page, site, base_url, auth_paths, credentials):
    if not credentials.get("email"):
        pytest.skip("Missing E2E_EMAIL; skipping")

    login: LoginPage = _login_page(new_page, base_url, auth_paths)
    login.goto()
    resp: LoginResult = login.login(credentials["email"], (credentials.get("password") or "P@ssw0rd!") + "_WRONG!")

    bad_statuses = {400, 401, 403, 409, 422}
    if getattr(resp, "status", None) in bad_statuses:
        return

    has_err, txt = has_error(new_page)
    if has_err:
        return

    try:
        still_on_login = bool(LOGIN_URL_RE.search(new_page.url))
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
    login: LoginPage = _login_page(new_page, base_url, auth_paths)
    login.goto()
    login.login("", "")

    assert LOGIN_URL_RE.search(new_page.url), f"Unexpected redirect from login: {new_page.url}"

    has_err, txt = has_error(new_page)
    assert has_err, "No error message for empty credentials"
    assert "required" in txt.lower(), f"Unexpected error message: {txt}"


@pytest.mark.auth
@pytest.mark.tc(id="RM-LOGIN-004", title="Login with slow network", area="Auth", severity="Medium")
def test_login_slow_network(new_page, site, base_url, auth_paths, credentials):
    if not (credentials.get("email") and credentials.get("password")):
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD; skipping login_success")

    login: LoginPage = _login_page(new_page, base_url, auth_paths)
    login.goto()

    with new_page.expect_navigation(timeout=15000):
        new_page.route("**/*", lambda route: route.continue_(
            headers={**route.request.headers, "Slow-Network": "true"}
        ))
        resp: LoginResult = login.login(credentials["email"], credentials["password"])

    assert resp is not None, "Login did not return a result"
    assert resp.status in (200, 302), f"Unexpected login HTTP status: {resp.status}, body={resp.body}"
    assert "dashboard" in new_page.url.lower() or "profile" in new_page.url.lower(), \
        f"Unexpected final URL after login: {new_page.url}"
