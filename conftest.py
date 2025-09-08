import os
import pytest

# Lấy --base-url mặc định từ ENV (BASE_URL > BASE_URL_PROD)
def pytest_addoption(parser):
    parser.addoption(
        "--base-url",
        action="store",
        default=os.getenv("BASE_URL") or os.getenv("BASE_URL_PROD") or "",
        help="Base URL for E2E tests (default from ENV).",
    )

@pytest.fixture(scope="session")
def base_url(pytestconfig):
    return pytestconfig.getoption("--base-url")

@pytest.fixture(scope="session")
def site():
    return os.getenv("SITE", "default")

@pytest.fixture(scope="session")
def auth_paths():
    return {
        "login": os.getenv("LOGIN_PATH", "/login"),
        "register": os.getenv("REGISTER_PATH", "/register"),
    }

@pytest.fixture(scope="session")
def credentials():
    return {
        "email": os.getenv("E2E_EMAIL", ""),
        "password": os.getenv("E2E_PASSWORD", ""),
    }

# Plugin pytest-playwright không có 'new_page' -> tự tạo từ 'context'
@pytest.fixture
def new_page(context):
    page = context.new_page()
    try:
        yield page
    finally:
        try:
            page.close()
        except Exception:
            pass

# Ghi metadata cho pytest-html / pytest-metadata
def pytest_configure(config):
    md = getattr(config, "_metadata", None)
    if isinstance(md, dict):
        md["Base URL"] = config.getoption("--base-url") or ""
        md["CI"] = os.getenv("CI", "0")
