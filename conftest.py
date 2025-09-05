# conftest.py
import os
import pytest


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _split_csv(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


# ---- Session-level fixtures (đọc từ ENV) ----

@pytest.fixture(scope="session")
def site() -> str:
    return _env("SITE", "ratemate")


@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    # Ưu tiên ENV BASE_URL / BASE_URL_PROD; nếu trống thì thử --base-url của plugin base-url
    env_base = _env("BASE_URL") or _env("BASE_URL_PROD")
    try:
        cli_base = pytestconfig.getoption("--base-url") or ""
    except Exception:
        cli_base = ""
    return env_base or cli_base or ""


@pytest.fixture(scope="session")
def auth_paths() -> dict:
    return {
        "login": _env("LOGIN_PATH", "/en/login"),
        "register": _env("REGISTER_PATH", "/en/login"),
    }


@pytest.fixture(scope="session")
def credentials() -> dict:
    return {
        "email": _env("E2E_EMAIL"),
        "password": _env("E2E_PASSWORD"),
    }


@pytest.fixture(scope="session")
def public_routes() -> list[str]:
    # Ví dụ: "/,/login"
    return _split_csv(_env("PUBLIC_ROUTES", "/,/login"))


@pytest.fixture(scope="session")
def protected_routes() -> list[str]:
    # Ví dụ: "/store,/product,/QR"
    return _split_csv(_env("PROTECTED_ROUTES", "/store,/product,/QR"))


@pytest.fixture(scope="session")
def locale() -> str:
    # Dùng cho test i18n/link nếu cần
    return _env("LOCALE", "en")


# ---- Page-level fixture cho Playwright ----
# pytest-playwright cung cấp sẵn 'context'; ta tạo 'new_page' giống test đang dùng.

@pytest.fixture
def new_page(context):
    p = context.new_page()
    # Set timeout mặc định (ms) nếu có ENV TIMEOUT_MS, mặc định 60000
    try:
        to = int(_env("TIMEOUT_MS", "60000"))
        p.set_default_navigation_timeout(to)
        p.set_default_timeout(to)
    except Exception:
        pass
    yield p
    try:
        p.close()
    except Exception:
        pass


def pytest_configure(config):
    """Ghi Base URL vào metadata (nếu plugin pytest-metadata có mặt) để report dễ đọc."""
    try:
        base = _env("BASE_URL") or _env("BASE_URL_PROD")
        md = getattr(config, "_metadata", None)
        if isinstance(md, dict):
            md["Base URL"] = base
    except Exception:
        pass