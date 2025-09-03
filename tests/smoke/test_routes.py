import os
import re
import pytest

def _norm(p: str) -> str:
    return re.sub(r"/+$", "", p or "")

# Cho phép override đường dẫn login qua ENV
_LOGIN_PATHS = {
    _norm(os.getenv("LOGIN_PATH", "")),
    _norm(os.getenv("ALT_LOGIN_PATH", "")),
    "/en/login",
    "/login",
}
_LOGIN_PATHS = {p for p in _LOGIN_PATHS if p}

# Danh sách route cần login → lấy từ ENV để không trùng với auto-param "route"
_PROTECTED_ROUTES = {
    _norm(s) for s in re.split(r"[,\s]+", os.getenv("PROTECTED_ROUTES", "")) if s
}

@pytest.mark.smoke
def test_open_route_ok(new_page, base_url, route):
    target = _norm(route)
    new_page.goto(f"{base_url}{route}", wait_until="domcontentloaded", timeout=20000)
    final_url = new_page.url

    # Nếu route thuộc nhóm protected → kỳ vọng bị redirect về login
    if target in _PROTECTED_ROUTES:
        if any(re.search(re.escape(lp), final_url) for lp in _LOGIN_PATHS):
            return
        raise AssertionError(
            f"Protected route {route} should redirect to login; got: {final_url}"
        )

    # Route public → phải giữ nguyên (không bị redirect)
    assert re.search(re.escape(target), final_url), \
        f"URL mismatch for route {route}; final: {final_url}"


@pytest.mark.parametrize("protected_route", ["/store", "/profile", "/wallet"])
def test_protected_redirect_to_login(page, base_url, protected_route):
    page.goto(f"{base_url}{protected_route}")
    page.wait_for_load_state("domcontentloaded")
    assert "/login" in page.url
