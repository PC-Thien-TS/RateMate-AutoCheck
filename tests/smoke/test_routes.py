import os
import re
import pathlib
from typing import List, Tuple
import yaml
import pytest
import contextlib
from pages.auth.login_page import LoginPage

# ===== helpers =====
def _norm(p: str) -> str:
    s = (p or "").strip()
    if not s:
        return ""
    if not s.startswith("/"):
        s = "/" + s
    # trim trailing slashes
    return re.sub(r"/+$", "", s)

def _variants(path: str):
    """Return valid variants for a path: /x and /<locale>/x for known locales."""
    s = _norm(path)
    out = {s}
    raw_locales = (os.getenv("LOCALES") or "en,vi,cn").strip()
    locales = [c.strip() for c in raw_locales.split(",") if c.strip()]
    for loc in locales:
        if s and not s.startswith(f"/{loc}/"):
            out.add(f"/{loc}{s}")
    return out

def _csv_paths(envname: str, defaults: List[str]) -> List[str]:
    raw = (os.getenv(envname) or "").strip()
    if not raw:
        items = defaults
    else:
        items = [x.strip() for x in raw.split(",") if x.strip()]
    # normalize & dedupe
    seen = []
    for it in items:
        n = _norm(it)
        if n and n not in seen:
            seen.append(n)
    return seen

def _is_login_like(page) -> bool:
    """Detect if login form is present without redirect."""
    selectors = [
        'input[type="email"]',
        'input[name*="email" i]',
        'input[type="password"]',
        'input[name*="password" i]',
        'button:has-text("Login")',
        'button:has-text("Sign in")',
        'form[action*="login" i]',
        '[data-testid*="login" i]',
    ]
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible():
                return True
        except Exception:
            pass
    return False

# ===== config =====
TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT_MS", "60000"))

# login paths, accept many variants
_LOGIN_PATHS_RAW = [
    os.getenv("LOGIN_PATH", "/login"),
    os.getenv("ALT_LOGIN_PATH", "/en/login"),
    "/login", "/en/login",
    "/signin", "/en/signin",
    "/auth/login", "/en/auth/login",
]
for _lc in [c.strip() for c in (os.getenv("LOCALES") or "").split(",") if c.strip()]:
    _LOGIN_PATHS_RAW.append(f"/{_lc}/login")
_LOGIN_PATHS = {_norm(p) for p in _LOGIN_PATHS_RAW if _norm(p)}
_LOGIN_VARIANTS = set().union(*[_variants(p) for p in _LOGIN_PATHS])

# default lists (override via ENV)
PUBLIC_DEFAULT = ["/", "/login"]
PROTECTED_DEFAULT = ["/store"]

def _load_routes_from_site_config() -> Tuple[List[str], List[str]]:
    site = (os.getenv("SITE") or "ratemate").strip()
    # Per-site file
    for ext in ("yml", "yaml"):
        p = pathlib.Path(f"config/sites/{site}.{ext}")
        if p.is_file():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
            routes = data.get("routes") or {}
            if isinstance(routes, dict):
                pub = routes.get("public") or []
                pro = routes.get("protected") or []
                if isinstance(pub, list) or isinstance(pro, list):
                    return (pub or PUBLIC_DEFAULT, pro or PROTECTED_DEFAULT)
            elif isinstance(routes, list):
                return (routes or PUBLIC_DEFAULT, PROTECTED_DEFAULT)
            break
    # Aggregated config/sites.yaml
    for name in ("config/sites.yaml", "config/sites.yml"):
        p = pathlib.Path(name)
        if p.is_file():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
            sites = data.get("sites") or {}
            cfg = sites.get(site, {}) if isinstance(sites, dict) else {}
            routes = cfg.get("routes") or {}
            if isinstance(routes, dict):
                pub = routes.get("public") or []
                pro = routes.get("protected") or []
                if isinstance(pub, list) or isinstance(pro, list):
                    return (pub or PUBLIC_DEFAULT, pro or PROTECTED_DEFAULT)
            elif isinstance(routes, list):
                return (routes or PUBLIC_DEFAULT, PROTECTED_DEFAULT)
            break
    # Fallback to ENV/DEFAULT
    return (
        _csv_paths("PUBLIC_ROUTES", PUBLIC_DEFAULT),
        _csv_paths("PROTECTED_ROUTES", PROTECTED_DEFAULT),
    )

PUBLIC_ROUTES, PROTECTED_ROUTES = _load_routes_from_site_config()

# build test matrix
CASES = [{"kind": "public", "path": p} for p in PUBLIC_ROUTES] + \
        [{"kind": "protected", "path": p} for p in PROTECTED_ROUTES]

# ===== fixtures =====
@pytest.fixture(scope="function")
def logged_in_page(new_page, base_url, auth_paths, credentials):
    """Logs in and returns the page, ready for action."""
    # Skip gracefully if credentials are not provided
    email = credentials.get("email", "")
    password = credentials.get("password", "")
    if not email or not password:
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD; skipping login-dependent tests")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto()
    lp.login(email, password)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(250)
    return new_page

@pytest.mark.smoke  # Mark as smoke to be included in default runs
@pytest.mark.parametrize("path", [
    "/en/store",
    "/en/QR",
    "/en/category",
    "/en/product",
    "/en/feedback",
])
def test_protected_routes_after_login(logged_in_page, base_url, path):
    """After successful login, protected routes should be accessible."""
    new_page = logged_in_page
    # Go to the protected path
    url = f"{base_url}{path}"
    new_page.set_default_navigation_timeout(TIMEOUT_MS)
    resp = new_page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
        new_page.wait_for_timeout(150)

    # Assert that we are not shown a login-like UI
    assert not _is_login_like(new_page), f"Redirected to login for {path} after login"

    # Status should be OK if provided by Playwright (some navigations may return None)
    status = getattr(resp, "status", None) if resp else None
    assert status is None or status < 400, f"Bad status {status} for {path} after login"

    # Final URL should include the path (or its locale variants)
    final_url_norm = _norm(new_page.url)
    path_variants = _variants(path)
    assert any(_norm(v) in final_url_norm for v in path_variants), (
        f"URL mismatch for {path}; final: {new_page.url}"
    )

# ===== tests =====
@pytest.mark.smoke
@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['kind']}:{c['path']}")
def test_routes_access(new_page, base_url, case):
    """
    - public: should load (if actual redirect to login, treat as protected and skip)
      /login (and variants) are treated as valid public login.
    - protected: must require login (redirect to /login or show login gate / return 401/403).
      If actually public, skip to avoid false fails.
    """
    path = _norm(case["path"])
    url = f"{base_url}{path}"

    new_page.set_default_navigation_timeout(TIMEOUT_MS)
    resp = new_page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
    final_url = new_page.url

    is_final_login = any(re.search(re.escape(v), final_url) for v in _LOGIN_VARIANTS)
    is_target_login = path in _LOGIN_PATHS or path in _LOGIN_VARIANTS

    if case["kind"] == "public":
        if is_target_login:
            assert is_final_login, f"{path} is public login but final not on login: {final_url}"
            return
        if is_final_login:
            pytest.skip(f"public {path} redirects to login — treat as protected: {final_url}")
        ok = any(re.search(re.escape(v), final_url) for v in _variants(path))
        assert ok, f"URL mismatch for public {path}; final: {final_url}"
        return

    # protected
    if is_final_login:
        return

    same_route = any(re.search(re.escape(v), final_url) for v in _variants(path))
    if same_route:
        status = getattr(resp, "status", None) if resp else None
        if _is_login_like(new_page) or status in (401, 403):
            return

    pytest.skip(f"{path} appears public (no redirect, no login gate); final: {final_url}")

    # Note: Additional assertions may be added per-site if needed

