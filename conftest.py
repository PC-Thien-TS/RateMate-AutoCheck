# conftest.py — chỉ Python fixtures cho pytest/playwright

import os
import pytest

# Set mặc định để tests ổn định nếu env chưa khai báo
os.environ.setdefault("PUBLIC_ROUTES", "/,/login")
os.environ.setdefault("PROTECTED_ROUTES", "/store,/product,/QR")

@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL cho site; ưu tiên BASE_URL, rồi BASE_URL_PROD, rồi default."""
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

# === FIX CHÍNH: bổ sung fixture `new_page` mà tests đang gọi ===
@pytest.fixture
def new_page(context):
    """
    Tạo 1 Page mới từ BrowserContext của pytest-playwright.
    Đảm bảo đóng sau khi test kết thúc.
    """
    page = context.new_page()
    try:
        yield page
    finally:
        try:
            page.close()
        except Exception:
            pass
