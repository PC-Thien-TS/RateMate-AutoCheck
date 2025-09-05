# conftest.py — chỉ Python, KHÔNG dán nội dung YAML của workflow vào đây!

import os
import pytest

# Một số test có thể đọc env trực tiếp; set default để ổn định
os.environ.setdefault("PUBLIC_ROUTES", "/,/login")
os.environ.setdefault("PROTECTED_ROUTES", "/store,/product,/QR")

@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL cho site, ưu tiên BASE_URL, fallback BASE_URL_PROD."""
    return os.getenv("BASE_URL") or os.getenv("BASE_URL_PROD") or "https://store.ratemate.top"

@pytest.fixture(scope="session")
def site() -> str:
    """Tên site để _factory() định tuyến đúng page objects."""
    return os.getenv("SITE") or "ratemate"

@pytest.fixture(scope="session")
def auth_paths() -> dict:
    """Đường dẫn login/register để page object sử dụng."""
    return {
        "login": os.getenv("LOGIN_PATH", "/login"),
        "register": os.getenv("REGISTER_PATH", "/login"),
    }

@pytest.fixture(scope="session")
def locale() -> str:
    """Ngôn ngữ mặc định cho các test i18n (nếu cần)."""
    return os.getenv("LOCALE", "en")

@pytest.fixture(scope="session")
def credentials() -> dict:
    """Thông tin đăng nhập cho test auth; nếu trống, test sẽ tự skip."""
    return {
        "email": os.getenv("E2E_EMAIL", ""),
        "password": os.getenv("E2E_PASSWORD", ""),
    }
