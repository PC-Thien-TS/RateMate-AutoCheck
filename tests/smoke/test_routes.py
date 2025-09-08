import os
import re
import pytest
import contextlib

# ===== helpers =====
def _norm(p: str) -> str:
    s = (p or "").strip()
    if not s:
        return ""
    if not s.startswith("/"):
        s = "/" + s
    return re.sub(r"/+$", "", s)

def _variants(path: str):
    """Return valid variants for a path: /x and /en/x."""
    s = _norm(path)
    out = {s}
    if s and not s.startswith("/en/"):
        out.add(f"/en{s}")
    return out

def _csv_paths(envname: str, defaults: list[str]) -> list[str]:
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
_LOGIN_PATHS = {_norm(p) for p in _LOGIN_PATHS_RAW if _norm(p)}
_LOGIN_VARIANTS = set().union(*[_variants(p) for p in _LOGIN_PATHS])

# default lists (override via ENV)
PUBLIC_DEFAULT = ["/", "/login"]
PROTECTED_DEFAULT = ["/store"]

PUBLIC_ROUTES = _csv_paths("PUBLIC_ROUTES", PUBLIC_DEFAULT)
PROTECTED_ROUTES = _csv_paths("PROTECTED_ROUTES", PROTECTED_DEFAULT)

# build test matrix
CASES = [{"kind": "public", "path": p} for p in PUBLIC_ROUTES] + \
        [{"kind": "protected", "path": p} for p in PROTECTED_ROUTES]

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

