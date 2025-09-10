# -*- coding: utf-8 -*-
import os
import json
import pathlib
from typing import Dict, List

import pytest
import yaml


def _first_existing(*paths: str) -> str | None:
    for p in paths:
        if p and pathlib.Path(p).is_file():
            return p
    return None


def _load_site_config() -> Dict:
    site = (os.getenv("SITE") or "").strip() or "ratemate"
    per_site = _first_existing(f"config/sites/{site}.yml", f"config/sites/{site}.yaml")
    many_sites = _first_existing("config/sites.yaml", "config/sites.yml")

    cfg: Dict = {}
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
        cfg = {}

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


@pytest.fixture(scope="session")
def site() -> str:
    return (os.getenv("SITE") or "").strip() or "ratemate"


@pytest.fixture(scope="session")
def base_url(pytestconfig) -> str:
    cli = getattr(pytestconfig.option, "base_url", None)
    if cli:
        return str(cli).rstrip("/")
    env_url = (
        os.environ.get("BASE_URL")
        or os.environ.get("BASE_URL_PROD")
        or ""
    )
    return str(env_url).rstrip("/")


@pytest.fixture(scope="session")
def auth_paths() -> dict:
    return {
        "login": os.environ.get("LOGIN_PATH", "/en/login"),
        "register": os.environ.get("REGISTER_PATH", "/en/login"),
    }


@pytest.fixture(scope="session")
def credentials() -> dict:
    site_key = (os.getenv("SITE") or "ratemate").strip().upper()

    def pick(name: str) -> str:
        for envn in (
            f"E2E_{site_key}_{name}",
            f"{site_key}_E2E_{name}",
            f"E2E_{name}",
        ):
            val = os.getenv(envn)
            if val:
                return val
        return ""

    return {"email": pick("EMAIL"), "password": pick("PASSWORD")}


@pytest.fixture(scope="session")
def public_routes() -> List[str]:
    raw = os.environ.get("PUBLIC_ROUTES", "/,/login")
    return [s.strip() for s in str(raw).split(",") if s.strip()]


@pytest.fixture(scope="session")
def protected_routes() -> List[str]:
    raw = os.environ.get("PROTECTED_ROUTES", "/store,/product,/QR")
    return [s.strip() for s in str(raw).split(",") if s.strip()]


@pytest.fixture(scope="session")
def locales() -> dict[str, str]:
    raw = (os.getenv("LOCALES") or os.getenv("SITE_LOCALES") or "en").strip()
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
    labels = {"en": "English", "vi": "Tiếng Việt", "zh": "中文"}
    out = {}
    for c in codes:
        out[c] = labels.get(c, c)
    return out or {"en": "English"}


@pytest.fixture(scope="session")
def locale(locales) -> str:
    env = (os.getenv("LOCALE") or "").strip()
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


@pytest.fixture(scope="session")
def all_routes(public_routes, protected_routes):
    return (
        [{"kind": "public", "path": p} for p in public_routes]
        + [{"kind": "protected", "path": p} for p in protected_routes]
    )

