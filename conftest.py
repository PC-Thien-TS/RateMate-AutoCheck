# conftest.py
import os
import pytest

def _split_csv(val, default="en"):
    return [s.strip() for s in (val or default).split(",") if s.strip()]

def _routes_from_env(key, fallback):
    raw = os.getenv(key)
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return list(fallback)

# ================== CONFIG CHO TỪNG SITE ==================

def _cfg_ratemate_tuple():
    base_url = os.getenv("BASE_URL_PROD") or os.getenv("BASE_URL_STAGING") or os.getenv("BASE_URL")
    assert base_url, "Thiếu BASE_URL_PROD (hoặc BASE_URL_STAGING/BASE_URL) cho RateMate"
    auth_paths = {
        "login": os.getenv("LOGIN_PATH", "/en/login"),
        "register": os.getenv("REGISTER_PATH", "/en/login"),
    }
    credentials = {
        "email": os.getenv("LOGIN_EMAIL", ""),
        "password": os.getenv("LOGIN_PASSWORD", ""),
    }
    locales = _split_csv(os.getenv("LOCALES"), "en")
    routes = _routes_from_env(
        "SMOKE_ROUTES",
        ["/en/login", "/en/store", "/en/product", "/en/QR"],
    )
    return "ratemate", base_url.rstrip("/"), auth_paths, credentials, locales, routes

def _cfg_site2_tuple():
    base_url = os.getenv("BASE_URL_SITE2") or os.getenv("BASE_URL")
    assert base_url, "Thiếu BASE_URL_SITE2 (hoặc BASE_URL) cho website #2"
    auth_paths = {
        "login": os.getenv("LOGIN_PATH_SITE2", "/login"),
        "register": os.getenv("REGISTER_PATH_SITE2", "/register"),
    }
    credentials = {
        "email": os.getenv("LOGIN_EMAIL_SITE2") or os.getenv("LOGIN_EMAIL", ""),
        "password": os.getenv("LOGIN_PASSWORD_SITE2") or os.getenv("LOGIN_PASSWORD", ""),
    }
    locales = _split_csv(os.getenv("LOCALES_SITE2") or os.getenv("LOCALES"), "en")
    routes = _routes_from_env(
        "SMOKE_ROUTES_SITE2",
        ["/login", "/register"],  # bạn có thể set qua env để đúng web #2
    )
    return "site2", base_url.rstrip("/"), auth_paths, credentials, locales, routes

def _active_site_cfg():
    """Giữ đúng interface cũ: trả về (site, base_url, auth_paths, credentials, locales, routes)."""
    site = (os.getenv("SITE") or "ratemate").lower()
    return _cfg_site2_tuple() if site in ("site2", "web2", "second") else _cfg_ratemate_tuple()

# ================== PYTEST ==================

def pytest_configure(config):
    site, base_url, *_ = _active_site_cfg()
    try:
        config._metadata["SITE"] = site
        config._metadata["Base URL"] = base_url
    except Exception:
        pass

@pytest.fixture(scope="session")
def site():
    return _active_site_cfg()[0]

@pytest.fixture(scope="session")
def base_url():
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

@pytest.fixture
def new_page(page):
    return page
