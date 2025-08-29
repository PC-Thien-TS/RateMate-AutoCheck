# tests/smoke/test_routes.py
import re, pytest

@pytest.mark.smoke
def test_open_route_ok(new_page, base_url, route):
    new_page.goto(f"{base_url}{route}", wait_until="domcontentloaded", timeout=20000)
    assert re.search(re.escape(route.rstrip("/")), new_page.url), f"URL mismatch for route {route}"
