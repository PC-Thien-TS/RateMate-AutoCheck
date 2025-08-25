import pytest

@pytest.mark.parametrize("route", [], ids=[])
def dummy():  # tránh file rỗng
    pass

def pytest_generate_tests(metafunc):
    if "route" in metafunc.fixturenames:
        from conftest import _active_site_cfg
        _, _, _, _, _, routes = _active_site_cfg()
        metafunc.parametrize("route", routes, ids=routes)

def test_open_route_ok(new_page, base_url, route):
    new_page.goto(base_url + route)
    assert new_page.locator("body").count() == 1
