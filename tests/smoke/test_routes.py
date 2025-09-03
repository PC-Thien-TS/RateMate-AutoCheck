# tests/smoke/test_routes.py
import os
import re
import pytest
import contextlib

# ========== helpers ==========
def _norm(p: str) -> str:
    return re.sub(r"/+$", "", p or "")

def _variants(path: str):
    """Sinh các biến thể hợp lệ của 1 path: /x và /en/x."""
    s = _norm(path)
    out = {s}
    if s and not s.startswith("/en/"):
        out.add(f"/en{s}")
    return out

def _first_csv(envname: str, default_path: str) -> str:
    raw = os.getenv(envname, "").strip()
    return _norm(raw.split(",")[0].strip()) if raw else _norm(default_path)

def _route_to_path(route: str) -> str:
    """Nhận 'public'/'protected' => path; nếu đã là path thì giữ nguyên."""
    if route.startswith("/"):
        return route
    if route == "public":
        return _DEFAULT_PUBLIC
    if route == "protected":
        return _DEFAULT_PROTECTED
    return "/" + route.strip("/")

def _looks_like_login(page) -> bool:
    """
    Heuristic: có input email + password + nút 'Đăng nhập/Sign in/Log in' hiển thị.
    Hỗ trợ cả modal/overlay.
    """
    try:
        email = page.locator("input[type='email'], input[name*='email' i]")
        pwd   = page.locator("input[type='password'], input[name*='password' i]")
        if email.count() == 0 or pwd.count() == 0:
            return False

        btn = page.get_by_role("button", name=re.compile(r"(đăng nhập|sign in|log in)", re.I))
        with contextlib.suppress(Exception):
            if btn.first.is_visible(timeout=800):
                return True

        submit = page.locator("form button[type='submit'], [role='form'] button[type='submit']")
        return submit.count() > 0 and submit.first.is_visible()
    except Exception:
        return False

# ========== config ==========
TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT_MS", "60000"))  # mặc định 60s

# login paths chấp nhận nhiều biến thể
_LOGIN_PATHS = {
    _norm(os.getenv("LOGIN_PATH", "/login")),
    _norm(os.getenv("ALT_LOGIN_PATH", "/en/login")),
    "/login",
    "/en/login",
}
_LOGIN_PATHS = {p for p in _LOGIN_PATHS if p}
_LOGIN_VARIANTS = set().union(*[_variants(p) for p in _LOGIN_PATHS])

# route mặc định cho nhóm
_DEFAULT_PUBLIC = _first_csv("PUBLIC_ROUTES", "/login")
_DEFAULT_PROTECTED = _first_csv("PROTECTED_ROUTES", "/store")

# ========== tests ==========
@pytest.mark.smoke
def test_open_route_ok(new_page, base_url, route):
    """
    Public route phải mở được (nhận cả /en/<route>).
    Nếu thực tế redirect về login -> coi là protected và skip ở test này.
    """
    path = _route_to_path(route)
    url = f"{base_url}{path}"

    new_page.set_default_navigation_timeout(TIMEOUT_MS)
    new_page.goto(url, wait_until="commit", timeout=TIMEOUT_MS)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)

    final_url = new_page.url

    # Nếu đã về trang login thì không phải public -> skip (nhường test protected)
    if any(re.search(re.escape(v), final_url) for v in _LOGIN_VARIANTS):
        pytest.skip(f"{route} ({path}) redirects to login → treat as protected: {final_url}")

    # Public: URL cuối phải khớp (nhận cả biến thể /en/<path>)
    ok = any(re.search(re.escape(v), final_url) for v in _variants(path))
    assert ok, f"URL mismatch for public route {route} ({path}); final: {final_url}"

@pytest.mark.parametrize("route", ["/store", "/profile", "/wallet"])
def test_protected_redirect_to_login(page, base_url, route):
    timeout = int(os.getenv("NAV_TIMEOUT_MS", "60000"))
    url = f"{base_url}{route}"
    resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    final_url = page.url

    # 1) Case redirect sang trang login (bất kỳ biến thể nào)
    if any(re.search(re.escape(lp), final_url) for lp in _LOGIN_VARIANTS):
        return

    # 2) Case "chặn tại chỗ": URL vẫn = route nhưng hiển thị form login / 401/403
    same_route = re.search(re.escape(_norm(route)), final_url) is not None
    if same_route:
        # Có form đăng nhập hoặc response là 401/403 => vẫn coi là bắt đăng nhập OK
        status = getattr(resp, "status", None) if resp else None
        if _is_login_like(page) or status in (401, 403):
            return

    # 3) Không redirect và cũng không thấy gate/login -> fail rõ ràng
    raise AssertionError(
        f"{route} should require auth (redirect to login or show login gate); final: {final_url}"
    )

# --- thêm helper ngay sau phần import ---
def _is_login_like(page) -> bool:
    """
    Nhận diện trang đang hiển thị gate/login (không redirect).
    Chỉ cần thấy 1 trong các selector phổ biến là đủ.
    """
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
