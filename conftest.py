# conftest.py — shared fixtures & runtime patches for Playwright tests

import os
import pytest
from typing import Generator

# ---------- Session-level config/fixtures ----------

@pytest.fixture(scope="session")
def site() -> str:
    """Tên site hiện tại (dùng để chọn PageObject phù hợp)."""
    return (os.getenv("SITE") or "").strip() or "ratemate"


@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    """
    Lấy base-url từ --base-url (plugin pytest-base-url) nếu có,
    nếu không thì fallback sang biến môi trường.
    Trả về dạng không có dấu '/' ở cuối để tránh '//'.
    """
    cli = getattr(pytestconfig.option, "base_url", None)
    if cli:
        return str(cli).rstrip("/")
    env_url = (
        os.environ.get("BASE_URL")
        or os.environ.get("BASE_URL_PROD")
        or ""
    )
    return env_url.rstrip("/")


@pytest.fixture(scope="session")
def auth_paths() -> dict:
    """
    Đường dẫn trang login/register. CI của bạn đang set:
      LOGIN_PATH=/en/login
      REGISTER_PATH=/en/login
    """
    return {
        "login": os.environ.get("LOGIN_PATH", "/en/login"),
        "register": os.environ.get("REGISTER_PATH", "/en/login"),
    }


@pytest.fixture(scope="session")
def credentials() -> dict:
    """Email/Password test lấy từ secrets CI (E2E_EMAIL / E2E_PASSWORD)."""
    return {
        "email": os.environ.get("E2E_EMAIL", ""),
        "password": os.environ.get("E2E_PASSWORD", ""),
    }


@pytest.fixture(scope="session")
def public_routes() -> list[str]:
    raw = os.environ.get("PUBLIC_ROUTES", "/,/login")
    return [s.strip() for s in raw.split(",") if s.strip()]


@pytest.fixture(scope="session")
def protected_routes() -> list[str]:
    raw = os.environ.get("PROTECTED_ROUTES", "/store,/product,/QR")
    return [s.strip() for s in raw.split(",") if s.strip()]


# ✅ FIX i18n: thêm fixture 'locales' cho tests/i18n/test_language_switch.py
@pytest.fixture(scope="session")
def locales() -> dict[str, str]:
    """
    Map mã ngôn ngữ -> label hiển thị trên UI.
    Sửa label cho khớp chính xác UI nếu cần (vd: 'Vietnamese' vs 'Tiếng Việt').
    """
    return {
        "en": "English",
        "vi": "Tiếng Việt",
    }


# ---------- Page / Browser-level fixtures ----------

@pytest.fixture
def new_page(context):
    """
    Alias tiện dùng: mỗi test có 1 Page riêng từ Context mặc định của plugin.
    Thiết lập timeout mặc định để tránh treo lâu.
    """
    page = context.new_page()
    page.set_default_timeout(30_000)             # 30s cho actions
    page.set_default_navigation_timeout(45_000)  # 45s cho nav
    try:
        yield page
    finally:
        try:
            page.close()
        except Exception:
            pass


# ---------- Runtime patch cho login_page._fill_force ----------

@pytest.fixture(scope="session", autouse=True)
def _patch_login_fill_force():
    """
    Tránh treo khi dùng Locator.type: chuyển sang fill() + fallback evaluate().
    Patch này chạy tự động ở session để không phải sửa mã nguồn pages/.
    """
    try:
        from pages import common_helpers as _ch  # type: ignore
    except Exception:
        # Nếu dự án không có module này (hoặc tên khác), bỏ qua patch
        return

    def _fill_force(locator, value, timeout: int = 10_000):
        # đảm bảo element sẵn sàng
        locator.wait_for(state="visible", timeout=timeout)
        try:
            # clear + fill nhanh, tránh gõ từng kí tự
            locator.click()
            locator.fill("")  # clear
            locator.fill(str(value), timeout=timeout)
        except Exception:
            # Fallback JS: set trực tiếp value và phát sự kiện
            locator.evaluate(
                """(el, v) => {
                    el.focus();
                    el.value = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.value = String(v);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                str(value),
            )

    # gắn patch
    try:
        _ch.fill_force = _fill_force  # type: ignore[attr-defined]
    except Exception:
        pass


# ---------- Locale (single) for tests expecting `locale` fixture ----------

import os as _os

@pytest.fixture(scope="session")
def locale(locales) -> str:
    """Active locale code used in some smoke tests (defaults to 'en')."""
    env = (_os.getenv("LOCALE") or "").strip()
    if env:
        return env
    try:
        if isinstance(locales, dict):
            if "en" in locales:
                return "en"
            keys = list(locales.keys())
            return keys[0] if keys else "en"
    except Exception:
        pass
    return "en"


# Combined route cases for parametrized smoke tests (alternative to inline CASES)
@pytest.fixture(scope="session")
def all_routes(public_routes, protected_routes):
    return (
        [{"kind": "public", "path": p} for p in public_routes]
        + [{"kind": "protected", "path": p} for p in protected_routes]
    )
