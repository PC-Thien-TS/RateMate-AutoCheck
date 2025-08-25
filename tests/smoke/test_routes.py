import pytest

@pytest.mark.parametrize("route", [], ids=[])
def dummy():
    pass

def pytest_generate_tests(metafunc):
    if "route" in metafunc.fixturenames:
        from conftest import routes as _routes  # fixture factory
        # Lấy giá trị thực tế của fixture session
        # (hack gọn: gọi hàm _active_site_cfg ở conftest là tránh; nhưng giờ đã có fixture)
        # Cách đơn giản: import _active_site_cfg hoặc map sẵn ở đây:
        from conftest import _active_site_cfg
        _, _, _, _, _, rs = _active_site_cfg()
        metafunc.parametrize("route", rs, ids=rs)

def test_open_route_ok(new_page, base_url, route):
    new_page.goto(base_url + route)
    assert new_page.locator("body").count() == 1
