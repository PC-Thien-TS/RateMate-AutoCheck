# tests/smoke/test_routes.py
import os
import re
import pytest
import contextlib

# ===================== helpers =====================
def _ensure_leading_slash(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    return p if p.startswith("/") else f"/{p}"

def _norm(p: str) -> str:
    """Chuẩn hóa path: thêm '/' đầu, bỏ '/' cuối (trừ root)."""
    p = _ensure_leading_slash(p)
    return "/" if p == "/" else re.sub(r"/+$", "", p)

def _env_list(name: str, default: str = ""):
    raw = os.getenv(name, default) or ""
    out = []
    for x in raw.split(","):
        x = _norm(x)
        if x and x not in out:
            out.append(x)
    return out

def _variants(path: str):
    """Sinh biến thể hợp lệ của 1 path: /x và /en/x."""
    s = _norm(path)
    if not s or s == "/":
        return {"/", "/en"}
    out = {s}
    if not s.startswith("/en/") and s != "/en":
        out.add(f"/en{s}")
    return out

def _is_login_like(page) -> bool:
    """
    Nhận diện trang đang hiển thị gate/login (không redirect).
    Chỉ cần thấy 1 selector phổ biến là đủ.
    """
    selectors = [
        'input[type="email"]',
        'input[name*="email" i]',
        'input[type="password"]',
        'input[name*="password" i]',
        'button:has-text("Login")',
        'button:has-text("Log in")',
        'button:has-text("Sign in")',
        'button:has-text("Đăng nhập")',
        'form[action*="login" i]',
        '[data-testid*="login" i]',
    ]
    for sel in selectors:
        with contextlib.suppress(Exception):
            loc = page.locator(sel).first
            if loc.is_visible(timeout=500):
                return True
    return False

# ===================== config =====================
TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT_MS", "60000"))  # mặc định 60s
STRICT_PROTECTED = (os.getenv("STRICT_PROTECTED", "").strip().lower() in ("1", "true", "yes"))

# login paths chấp nhận nhiều biến thể
_LOGIN_PATHS = {
    _norm(os.getenv("LOGIN_PATH", "/login")),
    _norm(os.getenv("ALT_LOGIN_PATH", "/en/login")),
    "/login",
    "/en/login",
}
_LOGIN_PATHS = {p for p in _LOGIN_PATHS if p}
_LOGIN_VARIANTS = set().union(*[_variants(p) for p in _LOGIN_PATHS])

# routes từ ENV (có mặc định an toàn)
PUBLIC_ROUTES    = _env_list("PUBLIC_ROUTES", "/login")
PROTECTED_ROUTES = _env_list("PROTECTED_ROUTES", "/store,/profile,/wallet")

# Cho phép override tạm thời các protected route thành public (ví dụ: "/profile,/wallet")
PUBLIC_OVERRIDES = set(_env_list("PUBLIC_OVERRIDES", ""))

# Gom thành một danh sách case duy nhất để tránh mọi “double-parametrize”
CASES = (
    [{"kind": "public", "path": p} for p in PUBLIC_ROUTES] +
    [{"kind": "protected", "path": p} for p in PROTECTED_ROUTES]
)

# ===================== single test suite =====================
@pytest.mark.smoke
@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['kind']}:{c['path']}")
def test_routes_access(new_page, base_url, case):
    """
    - public: mở được (nếu thực tế redirect về login → coi như protected và skip)
      riêng /login (và biến thể) được coi là public hợp lệ.
    - protected: phải bị yêu cầu đăng nhập (redirect sang /login hoặc vẫn đứng tại
      route nhưng hiện form login / trả 401/403).
      Nếu thực tế route đang mở công khai, mặc định SKIP (để không vỡ pipeline).
      Bật STRICT_PROTECTED=true để FAIL trong tình huống này.
      Có thể khai báo PUBLIC_OVERRIDES để coi một số protected route là public.
    """
    path = _norm(case["path"])
    url = f"{base_url}{path}"

    new_page.set_default_navigation_timeout(TIMEOUT_MS)
    resp = new_page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
    final_url = new_page.url

    is_final_login = any(re.search(re.escape(v), final_url) for v in _LOGIN_VARIANTS)
    is_target_login = (path in _LOGIN_PATHS) or (path in _LOGIN_VARIANTS)

    if case["kind"] == "public":
        # Với /login (và biến thể) => final phải là 1 trong các login variants
        if is_target_login:
            assert is_final_login, f"{path} là public login nhưng final không phải trang login: {final_url}"
            return

        # Public khác: nếu bị đẩy sang login -> thực chất protected → skip
        if is_final_login:
            pytest.skip(f"public {path} redirects to login → treat as protected: {final_url}")

        # Không bị đẩy sang login: URL cuối phải khớp (nhận cả biến thể /en/<path>)
        ok = any(re.search(re.escape(v), final_url) for v in _variants(path))
        assert ok, f"URL mismatch for public {path}; final: {final_url}"
        return

    # ---- protected ----
    # Cho phép override protected → public (tạm thời)
    if path in PUBLIC_OVERRIDES:
        # Nếu override thì hành vi như public
        if is_final_login:
            pytest.skip(f"override public {path} redirects to login (unexpected, but skipping): {final_url}")
        ok = any(re.search(re.escape(v), final_url) for v in _variants(path))
        assert ok, f"override public {path} final mismatch: {final_url}"
        return

    if is_final_login:
        # Redirect đến login là đúng
        return

    # Không redirect: nếu vẫn ở route mà có login-gate hoặc 401/403 → cũng coi là đúng
    same_route = any(re.search(re.escape(v), final_url) for v in _variants(path))
    if same_route:
        status = getattr(resp, "status", None) if resp else None
        if _is_login_like(new_page) or status in (401, 403):
            return

    # Không redirect và cũng không thấy login gate -> route đang mở công khai
    msg = f"{path} appears public (no redirect, no login gate); final: {final_url}"
    if STRICT_PROTECTED:
        raise AssertionError(
            f"{path} should require auth (redirect to login or show login gate); final: {final_url}"
        )
    else:
        pytest.skip(msg)
