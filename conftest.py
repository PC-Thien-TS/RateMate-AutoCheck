# conftest.py — shared fixtures & runtime patches for Playwright tests

import os
import pathlib
from typing import Generator

import pytest
import yaml

# ---------- Config loading from YAML (optional multi-site support) ----------

def _first_existing(*paths: str) -> str | None:
    for p in paths:
        if p and pathlib.Path(p).is_file():
            return p
    return None


def _load_site_config() -> dict:
    site = (os.getenv("SITE") or "").strip() or "ratemate"
    # Per-site file takes precedence, then aggregated sites.yaml
    per_site = _first_existing(f"config/sites/{site}.yml", f"config/sites/{site}.yaml")
    many_sites = _first_existing("config/sites.yaml", "config/sites.yml")

    cfg: dict = {}
    try:
        if per_site:
            with open(per_site, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        elif many_sites:
            with open(many_sites, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            sites = (raw.get("sites") or {}) if isinstance(raw, dict) else {}
            cfg = sites.get(site, {}) if isinstance(sites, dict) else {}
        else:
            cfg = {}
    except Exception:
        cfg = {}

    if not isinstance(cfg, dict):
        return {}

    # Normalize both flat style and nested auth_paths/routes
    base_url = cfg.get("base_url") or cfg.get("BASE_URL")
    if isinstance(cfg.get("auth_paths"), dict):
        login_path = cfg.get("auth_paths", {}).get("login")
        register_path = cfg.get("auth_paths", {}).get("register")
    else:
        login_path = cfg.get("login_path") or cfg.get("LOGIN_PATH")
        register_path = cfg.get("register_path") or cfg.get("REGISTER_PATH")

    routes_public = None
    routes_protected = None
    routes = cfg.get("routes")
    if isinstance(routes, dict):
        rp = routes.get("public")
        rr = routes.get("protected")
        routes_public = rp if isinstance(rp, list) else None
        routes_protected = rr if isinstance(rr, list) else None
    elif isinstance(routes, list):
        routes_public = routes

    locales = cfg.get("locales") if isinstance(cfg.get("locales"), list) else None

    out = {
        "base_url": (str(base_url).rstrip("/") if base_url else None),
        "login_path": login_path,
        "register_path": register_path,
        "routes_public": routes_public,
        "routes_protected": routes_protected,
        "locales": locales,
    }
    return {k: v for k, v in out.items() if v}


@pytest.fixture(scope="session", autouse=True)
def _apply_site_config_to_env() -> None:
    cfg = _load_site_config()
    if not cfg:
        return
    def _set(name: str, value):
        if value is None:
            return
        if os.getenv(name) in (None, ""):
            os.environ[name] = str(value)
    _set("BASE_URL", cfg.get("base_url"))
    _set("LOGIN_PATH", cfg.get("login_path"))
    _set("REGISTER_PATH", cfg.get("register_path"))
    if os.getenv("ALT_LOGIN_PATH") in (None, ""):
        alt = cfg.get("login_path") or cfg.get("register_path")
        if alt:
            os.environ["ALT_LOGIN_PATH"] = str(alt)
    if cfg.get("routes_public"):
        _set("PUBLIC_ROUTES", ",".join(cfg["routes_public"]))
    if cfg.get("routes_protected"):
        _set("PROTECTED_ROUTES", ",".join(cfg["routes_protected"]))
    if cfg.get("locales"):
        _set("LOCALES", ",".join(cfg["locales"]))

    # Merge discovered routes if present and not already set by env
    site = (os.getenv("SITE") or "").strip() or "ratemate"
    disc_path = pathlib.Path(f"config/discovered/{site}.json")
    if disc_path.is_file():
        try:
            import json
            data = json.loads(disc_path.read_text(encoding="utf-8")) or {}
            if not os.getenv("PUBLIC_ROUTES") and isinstance(data.get("public"), list):
                os.environ["PUBLIC_ROUTES"] = ",".join(str(x) for x in data["public"] if x)
            if not os.getenv("PROTECTED_ROUTES") and isinstance(data.get("protected"), list):
                os.environ["PROTECTED_ROUTES"] = ",".join(str(x) for x in data["protected"] if x)
            if not os.getenv("BASE_URL") and data.get("base_url"):
                os.environ["BASE_URL"] = str(data["base_url"]).rstrip("/")
            if not os.getenv("LOGIN_PATH") and data.get("login_path"):
                os.environ["LOGIN_PATH"] = str(data["login_path"])
        except Exception:
            pass


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


# Override locales fixture with environment-driven version
@pytest.fixture(scope="session")
def locales() -> dict[str, str]:
    """Locale map driven by LOCALES env (csv). Defaults to English only."""
    raw = (os.getenv("LOCALES") or os.getenv("SITE_LOCALES") or "en").strip()
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
    labels = {"en": "English", "vi": "Tiếng Việt"}
    out = {}
    for c in codes:
        out[c] = labels.get(c, c)
    return out or {"en": "English"}
