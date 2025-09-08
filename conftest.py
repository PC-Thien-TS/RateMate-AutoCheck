import os
import pytest
from typing import Generator

# --- helpers ---
def _env_base_url() -> str:
    val = (os.getenv("BASE_URL") or os.getenv("BASE_URL_PROD") or "").strip()
    return val.rstrip("/")

# --- fixtures ---

@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    """
    Ưu tiên giá trị từ CLI --base-url (plugin pytest-base-url đã cung cấp).
    Nếu không có thì fallback sang ENV (BASE_URL/BASE_URL_PROD).
    """
    cli = getattr(pytestconfig.option, "base_url", None)
    if cli:
        return str(cli).rstrip("/")
    return _env_base_url()

@pytest.fixture(scope="session")
def site() -> dict:
    return {
        "name": os.getenv("SITE", ""),
        "env": os.getenv("ENV", ""),
        "base_url": _env_base_url(),
    }

@pytest.fixture(scope="session")
def auth_paths() -> dict:
    return {
        "login": os.getenv("LOGIN_PATH", "/login"),
        "register": os.getenv("REGISTER_PATH", "/register"),
    }

@pytest.fixture(scope="session")
def credentials() -> dict:
    email = os.getenv("E2E_EMAIL") or ""
    password = os.getenv("E2E_PASSWORD") or ""
    if not email or not password:
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD; skipping auth cases")
    return {"email": email, "password": password}

@pytest.fixture
def new_page(context) -> Generator:
    """
    Tạo một Page mới cho mỗi test (pytest-playwright cung cấp `context`).
    """
    page = context.new_page()
    try:
        yield page
    finally:
        page.close()

# Giảm tải bộ nhớ cho Playwright trên CI
@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 800},
        "ignore_https_errors": True,
        "accept_downloads": False,
    }
