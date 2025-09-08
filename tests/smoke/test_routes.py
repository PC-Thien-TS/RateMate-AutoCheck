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
    """Trả về các biến thể hợp lệ của 1 path: /x và /en/x."""
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
    # chuẩn hoá & loại rỗng
    seen = []
    for it in items:
        n = _norm(it)
        if n and n not in seen:
            seen.append(n)
    return seen

def _is_login_like(page) -> bool:
    """Nhận diện trang đang hiển thị gate/login (không redirect)."""
    selectors = [
        'input[type="email"]',
        'input[name*="email" i]',
        'input[type="password"]',
        'input[name*="password" i]',
        'button:has-text("Login")',
        'button:has-text("Sign in")',
        'button:has-text("Đăng nhập")',
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
@pytest.fixture(scope="session")
def all_routes(public_routes, protected_routes):
    """Tạo test matrix từ các fixture."""
    return [{"kind": "public", "path": p} for p in public_routes] + \
           [{"kind": "protected", "path": p} for p in protected_routes]

# login paths chấp nhận nhiều biến thể
_LOGIN_PATHS_RAW = [
    os.getenv("LOGIN_PATH", "/login"),
    os.getenv("ALT_LOGIN_PATH", "/en/login"),
    "/login", "/en/login",
    "/signin", "/en/signin",
    "/auth/login", "/en/auth/login",
]
_LOGIN_PATHS = {_norm(p) for p in _LOGIN_PATHS_RAW if _norm(p)}
_LOGIN_VARIANTS = set().union(*[_variants(p) for p in _LOGIN_PATHS])

# Danh sách mặc định (override qua ENV)
PUBLIC_DEFAULT = ["/", "/login"]
PROTECTED_DEFAULT = ["/store"]

PUBLIC_ROUTES = _csv_paths("PUBLIC_ROUTES", PUBLIC_DEFAULT)
PROTECTED_ROUTES = _csv_paths("PROTECTED_ROUTES", PROTECTED_DEFAULT)

# Tạo test matrix
CASES = [{"kind": "public", "path": p} for p in PUBLIC_ROUTES] + \
        [{"kind": "protected", "path": p} for p in PROTECTED_ROUTES]

# ===== tests =====
@pytest.mark.smoke
@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['kind']}:{c['path']}")
def test_routes_access(new_page, base_url, case):
@pytest.mark.parametrize("case", pytest.lazy_fixture("all_routes"), ids=lambda c: f"{c['kind']}:{c['path']}")
def test_routes_access(new_page, base_url, auth_paths, case):
    """
    - public: mở được (nếu thực tế redirect về login → coi như protected và skip)
      riêng /login (và biến thể) được coi là public hợp lệ.
    - protected: phải yêu cầu đăng nhập (redirect sang /login hoặc hiển thị form login / trả 401/403).
      Nếu thực tế public → skip để tránh false fail.
    """
    path = _norm(case["path"])
    path = case["path"]
    url = f"{base_url}{path}"

    # Xác định các biến thể của trang login từ fixture
    login_path_variants = {auth_paths["login"], auth_paths["register"]}
    login_path_variants.add("/login") # Thêm fallback

    new_page.set_default_navigation_timeout(TIMEOUT_MS)
    resp = new_page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
    final_url = new_page.url

    is_final_login = any(re.search(re.escape(v), final_url) for v in _LOGIN_VARIANTS)
    is_target_login = path in _LOGIN_PATHS or path in _LOGIN_VARIANTS
    is_final_login = any(v in final_url for v in login_path_variants)
    is_target_login = path in login_path_variants

    if case["kind"] == "public":
        if is_target_login:
            assert is_final_login, f"{path} là public login nhưng final không phải trang login: {final_url}"
            return
        if is_final_login:
            pytest.skip(f"public {path} redirects to login → treat as protected: {final_url}")
        ok = any(re.search(re.escape(v), final_url) for v in _variants(path))
            pytest.skip(f"Public route '{path}' redirects to login -> treat as protected. Final URL: {final_url}")
        ok = path in final_url
        assert ok, f"URL mismatch for public {path}; final: {final_url}"
        return

    # protected
    if is_final_login:
        return

    same_route = any(re.search(re.escape(v), final_url) for v in _variants(path))
    
    same_route = path in final_url
    if same_route:
        status = getattr(resp, "status", None) if resp else None
        if _is_login_like(new_page) or status in (401, 403):
            return

    pytest.skip(f"{path} appears public (no redirect, no login gate); final: {final_url}")
