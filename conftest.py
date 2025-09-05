# conftest.py
import os
import pathlib
import pytest
from dotenv import load_dotenv

try:
    import yaml
except Exception:
    yaml = None

load_dotenv()

def _split_csv(val, default="en"):
    return [s.strip() for s in (val or default).split(",") if s.strip()]

def _routes_from_env(key, fallback):
    raw = os.getenv(key)
    return [p.strip() for p in raw.split(",") if p.strip()] if raw else list(fallback)

def _site_name() -> str:
    return (os.getenv("SITE") or "ratemate").strip()

def _load_yaml_for_site(site: str):
    cfg_dir = os.getenv("CONFIG_DIR") or "config/sites"
    p = pathlib.Path(cfg_dir) / f"{site}.yml"
    if p.exists() and yaml:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data
    return None

def _cfg_from_yaml(data: dict):
    base_url = (data.get("base_url") or "").rstrip("/")
    assert base_url, f"Thiếu base_url trong YAML"

    auth_paths = data.get("auth_paths") or {}
    login_path = auth_paths.get("login") or "/login"
    register_path = auth_paths.get("register") or "/register"

    cred = data.get("credentials") or {}
    email = cred.get("email") or os.getenv("E2E_EMAIL") or os.getenv("LOGIN_EMAIL", "")
    password = cred.get("password") or os.getenv("E2E_PASSWORD") or os.getenv("LOGIN_PASSWORD", "")

    locales = list(data.get("locales") or ["en"])
    routes = list(data.get("routes") or [login_path])

    return base_url, {"login": login_path, "register": register_path}, {"email": email, "password": password}, locales, routes

def _cfg_ratemate_env_only():
    env = (os.getenv("ENV") or "prod").lower()
    if env == "staging":
        base_url = os.getenv("BASE_URL_STAGING")
    else:
        base_url = os.getenv("BASE_URL_PROD")
    base_url = (base_url or os.getenv("BASE_URL") or "").rstrip("/")
    assert base_url, "Thiếu BASE_URL_PROD/BASE_URL_STAGING hoặc BASE_URL"

    auth_paths = {
        "login": os.getenv("LOGIN_PATH", "/en/login"),
        "register": os.getenv("REGISTER_PATH", "/en/register"),
    }
    credentials = {
        "email": os.getenv("E2E_EMAIL") or os.getenv("LOGIN_EMAIL", ""),
        "password": os.getenv("E2E_PASSWORD") or os.getenv("LOGIN_PASSWORD", ""),
    }
    locales = _split_csv(os.getenv("LOCALES"), "en")
    routes = _routes_from_env("SMOKE_ROUTES", ["/en/login", "/en/store", "/en/product", "/en/QR"])
    return base_url, auth_paths, credentials, locales, routes

def _active_site_cfg():
    """
    Trả về tuple: (site, base_url, auth_paths, credentials, locales, routes)
    - Nếu DISABLE_SITE_YAML=1 -> bỏ qua YAML, chỉ dùng ENV.
    - Mặc định: YAML-first; nếu không có YAML -> ENV-only.
    """
    site = _site_name()
    if os.getenv("DISABLE_SITE_YAML") == "1":
        base_url, auth_paths, credentials, locales, routes = _cfg_ratemate_env_only()
        return site, base_url, auth_paths, credentials, locales, routes

    y = _load_yaml_for_site(site)
    if y:
        base_url, auth_paths, credentials, locales, routes = _cfg_from_yaml(y)
        return site, base_url, auth_paths, credentials, locales, routes

    base_url, auth_paths, credentials, locales, routes = _cfg_ratemate_env_only()
    return site, base_url, auth_paths, credentials, locales, routes

def pytest_configure(config):
    site, base_url, *_ = _active_site_cfg()
    if not base_url:
        pytest.exit(
            "BASE_URL rỗng. Hãy truyền BASE_URL hoặc BASE_URL_PROD/BASE_URL_STAGING "
            "và/hoặc đặt DISABLE_SITE_YAML=1 để dùng ENV.", returncode=2
        )
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

def _already_parametrized(metafunc, arg: str) -> bool:
    # Nếu test đã có @pytest.mark.parametrize(..., include arg) thì không auto-param nữa
    for m in metafunc.definition.iter_markers(name="parametrize"):
        if not m.args:
            continue
        names = m.args[0]
        if isinstance(names, str):
            argnames = [n.strip() for n in names.split(",")]
        else:
            argnames = [str(n) for n in names]
        if arg in argnames:
            return True
    return False

def pytest_generate_tests(metafunc):
    if "route" in metafunc.fixturenames and not _already_parametrized(metafunc, "route"):
        _routes = _active_site_cfg()[5]
        metafunc.parametrize("route", _routes, ids=_routes or ["<no-routes>"])
    if "locale" in metafunc.fixturenames and not _already_parametrized(metafunc, "locale"):
        _locales = _active_site_cfg()[4]
        metafunc.parametrize("locale", _locales, ids=_locales or ["default"])
