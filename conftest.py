# conftest.py
import os
import pytest
from dotenv import load_dotenv

load_dotenv()  # đọc .env nếu có

def _split_csv(val, default="en"):
    return [s.strip() for s in (val or default).split(",") if s.strip()]

def _routes_from_env(key, fallback):
    raw = os.getenv(key)
    return [p.strip() for p in raw.split(",") if p.strip()] if raw else list(fallback)

# ======== CẤU HÌNH CHO 1 WEB: https://store.ratemate.top ========
def _cfg_ratemate_tuple():
    # Tôn trọng ENV=prod|staging, rồi mới fallback BASE_URL
    env = (os.getenv("ENV") or "prod").lower()
    if env == "staging":
        base_url = os.getenv("BASE_URL_STAGING")
    else:
        base_url = os.getenv("BASE_URL_PROD")
    base_url = base_url or os.getenv("BASE_URL")
    assert base_url, "Thiếu BASE_URL_PROD/BASE_URL_STAGING hoặc BASE_URL cho RateMate"

    auth_paths = {
        "login": os.getenv("LOGIN_PATH", "/en/login"),
        # nếu form đăng ký chung trang login, đổi mặc định này lại '/en/login'
        "register": os.getenv("REGISTER_PATH", "/en/register"),
    }
    credentials = {
        # Ưu tiên biến an toàn cho E2E test; fallback về biến cũ nếu chưa chuyển
        "email": os.getenv("E2E_EMAIL") or os.getenv("LOGIN_EMAIL", ""),
        "password": os.getenv("E2E_PASSWORD") or os.getenv("LOGIN_PASSWORD", ""),
    }
    locales = _split_csv(os.getenv("LOCALES"), "en")
    routes = _routes_from_env(
        "SMOKE_ROUTES",
        ["/en/login", "/en/store", "/en/product", "/en/QR"],
    )
    return "ratemate", base_url.rstrip("/"), auth_paths, credentials, locales, routes

def _active_site_cfg():
    """Trả về (site, base_url, auth_paths, credentials, locales, routes)."""
    return _cfg_ratemate_tuple()

# ================== PYTEST ==================
def pytest_configure(config):
    site, base_url, *_ = _active_site_cfg()
    md = getattr(config, "_metadata", None)
    if md is not None:
        md["SITE"] = site
        md["ENV"] = os.getenv("ENV", "prod")
        md["Base URL"] = base_url

@pytest.fixture(scope="session")
def site():
    return _active_site_cfg()[0]

@pytest.fixture(scope="session")
def base_url():
    # Khớp với plugin pytest-base-url nếu bạn dùng
    return _active_site_cfg()[1]

@pytest.fixture(scope="session")
def auth_paths():
    return _active_site_cfg()[2]

@pytest.fixture(scope="session")
def credentials():
    return _active_site_cfg()[3]

@pytest.fixture(scope="session")
def locales():
    return _active_site_cfg()[4]

@pytest.fixture(scope="session")
def routes():
    return _active_site_cfg()[5]

@pytest.fixture
def new_page(page):
    return page
