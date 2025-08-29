# tests/smoke/test_routes.py
import os
import re
import pytest

def _norm(p: str) -> str:
    return re.sub(r"/+$", "", p or "")

# Cho phép cấu hình đường dẫn login qua env; mặc định thử cả /en/login và /login
_LOGIN_PATHS = {
    _norm(os.getenv("LOGIN_PATH", "")),
    _norm(os.getenv("ALT_LOGIN_PATH", "")),
    "/en/login",
    "/login",
}
_LOGIN_PATHS = {p for p in _LOGIN_PATHS if p}  # loại phần tử rỗng

# Danh sách route cần login (bị redirect về login) – cấu hình qua env: PROTECTED_ROUTES="/en/store,/en/product,/en/QR"
_PROTECTED_ROUTES = {
    _norm(s) for s in re.split(r"[,\s]+", os.getenv("PROTECTED_ROUTES", "")) if s
}

@pytest.mark.smoke
def test_open_route_ok(new_page, base_url, route):
    target = _norm(route)
    new_page.goto(f"{base_url}{route}", wait_until="domcontentloaded", timeout=20000)
    final_url = new_page.url

    # Nếu là route protected và đang ở trang login -> pass
    if target in _PROTECTED_ROUTES:
        if any(re.search(re.escape(lp), final_url) for lp in _LOGIN_PATHS):
            return
        # Nếu không vào được login như kỳ vọng, fail rõ ràng
        raise AssertionError(
            f"Protected route {route} should redirect to login; got: {final_url}"
        )

    # Với route public, phải giữ nguyên route (không bị redirect)
    assert re.search(re.escape(target), final_url), \
        f"URL mismatch for route {route}; final: {final_url}"
