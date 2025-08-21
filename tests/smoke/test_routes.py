import os
import pytest

def _routes():
    # Lấy từ ENV hoặc mặc định
    routes_env = os.getenv("ROUTES", "/en/login,/en/store,/en/product,/en/QR")
    return [r.strip() for r in routes_env.split(",") if r.strip()]

@pytest.mark.smoke
@pytest.mark.parametrize("path", _routes())
def test_open_route_ok(new_page, base_url, path):
    url = f"{base_url}{path}"
    resp = new_page.goto(url, wait_until="domcontentloaded")
    # Nếu resp None (SPA), bỏ check status
    if resp:
        assert 200 <= resp.status < 400, f"HTTP {resp.status} for {url}"
    # Trang phải render được
    assert new_page.title() is not None
    assert new_page.content() is not None
