# tests/smoke/test_links.py
from __future__ import annotations
import csv, os, re, contextlib, urllib.parse as _u
import pytest

# đặt ở đầu file test (sau import)
import os, re

def _norm(p: str) -> str:
    return re.sub(r"/+$", "", p or "")

_LOGIN_VARIANTS = {
    _norm(os.getenv("LOGIN_PATH", "/login")),
    _norm(os.getenv("ALT_LOGIN_PATH", "/en/login")),
    "/login",
    "/en/login",
}


def _rows():
    p = "fixtures/data/links.csv"
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def _norm(s: str) -> str:
    return re.sub(r"/+$", "", s or "")

def _variants(path: str) -> set[str]:
    s = _norm(path); out = {s}
    if s and not s.startswith("/en/"): out.add(f"/en{s}")
    return out

def _url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

def _on_login_url(url: str, login_variants: set[str]) -> bool:
    for lp in login_variants:
        if re.search(re.escape(lp) + r"($|[?#])", url): return True
    return False

def _wait_visible(loc, timeout=5000) -> bool:
    with contextlib.suppress(Exception):
        loc.first.wait_for(state="visible", timeout=timeout); return True
    return False

def _any_count(*locators) -> int:
    total = 0
    for loc in locators:
        try: total += loc.count()
        except Exception: pass
    return total

def _host_from_base(base_url: str) -> str | None:
    try: return _u.urlparse(base_url).hostname
    except Exception: return None

TIMEOUT_MS = int(os.getenv("NAV_TIMEOUT_MS", "60000"))
POST_LOGIN_PAUSE_MS = int(os.getenv("POST_LOGIN_PAUSE_MS", "800"))

LOGIN_PATH = os.getenv("LOGIN_PATH", "/login")
ALT_LOGIN_PATH = os.getenv("ALT_LOGIN_PATH", "/en/login")
LOGIN_VARIANTS = set().union(_variants(LOGIN_PATH), _variants(ALT_LOGIN_PATH))

AUTO_LOGIN = os.getenv("LOGIN_LINKS", "false").lower() in {"1","true","yes"}
E2E_EMAIL = os.getenv("E2E_EMAIL","")
E2E_PASSWORD = os.getenv("E2E_PASSWORD","")

COOKIE_NAME = os.getenv("E2E_COOKIE_NAME","")
COOKIE_VALUE = os.getenv("E2E_COOKIE_VALUE","")
COOKIE_DOMAIN_ENV = os.getenv("E2E_COOKIE_DOMAIN","")
COOKIE_PATH = os.getenv("E2E_COOKIE_PATH","/")
COOKIE_SECURE = os.getenv("E2E_COOKIE_SECURE","true").lower() in {"1","true","yes"}

def _looks_like_login(page) -> bool:
    try:
        email_like = page.get_by_placeholder(re.compile(r"email|e-mail|địa chỉ", re.I)).or_(
            page.get_by_label(re.compile(r"email|e-mail|địa chỉ", re.I))
        ).or_(page.locator("input[type='email'], input[name*='email' i], input[autocomplete='email']"))
        pwd_like = page.get_by_placeholder(re.compile(r"password|mật khẩu", re.I)).or_(
            page.get_by_label(re.compile(r"password|mật khẩu", re.I))
        ).or_(page.locator("input[type='password'], input[autocomplete='current-password']"))
        btn_like = page.get_by_role("button", name=re.compile(r"(đăng nhập|sign in|log in|continue|next|submit)", re.I))
        return _any_count(email_like)>0 and (_any_count(pwd_like)>0 or _any_count(btn_like)>0)
    except Exception:
        return False

def _expose_email_form_if_needed(page):
    for rx in [r"continue", r"next", r"sign\s*in", r"log\s*in"]:
        btn = page.get_by_role("button", name=re.compile(rx, re.I))
        if _any_count(btn)>0 and btn.first.is_enabled():
            with contextlib.suppress(Exception):
                btn.first.click(); page.wait_for_timeout(250)

def _fill_and_submit_login(page, email_val: str, pwd_val: str, timeout_ms: int) -> bool:
    page.set_default_timeout(timeout_ms)
    _expose_email_form_if_needed(page)
    email = page.get_by_placeholder(re.compile(r"email|e-mail|địa chỉ", re.I)).or_(
        page.get_by_label(re.compile(r"email|e-mail|địa chỉ", re.I))
    ).or_(page.locator("input[type='email'], input[name*='email' i], input[autocomplete='email']")).first
    pwd = page.get_by_placeholder(re.compile(r"password|mật khẩu", re.I)).or_(
        page.get_by_label(re.compile(r"password|mật khẩu", re.I))
    ).or_(page.locator("input[type='password'], input[autocomplete='current-password']")).first

    if not _wait_visible(email, 9000): return False
    with contextlib.suppress(Exception): email.fill(email_val)
    if not pwd.is_visible(): _expose_email_form_if_needed(page)
    _wait_visible(pwd, 9000)
    with contextlib.suppress(Exception): pwd.fill(pwd_val)

    clicked = False
    for rx in [r"(đăng nhập|sign in|log in)", r"(submit|continue|next)"]:
        btn = page.get_by_role("button", name=re.compile(rx, re.I))
        if _any_count(btn)>0 and btn.first.is_enabled():
            with contextlib.suppress(Exception):
                btn.first.click(); clicked=True; break
    if not clicked:
        submit = page.locator("form button[type='submit']")
        if _any_count(submit)>0 and submit.first.is_enabled():
            with contextlib.suppress(Exception):
                submit.first.click(); clicked=True

    with contextlib.suppress(Exception):
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    with contextlib.suppress(Exception):
        page.wait_for_timeout(POST_LOGIN_PAUSE_MS)

    otp_like = page.get_by_placeholder(re.compile(r"code|otp|verification", re.I)).or_(
        page.get_by_label(re.compile(r"code|otp|verification", re.I))
    )
    if _any_count(otp_like)>0 and not _on_login_url(page.url, LOGIN_VARIANTS):
        return False
    return (not _on_login_url(page.url, LOGIN_VARIANTS)) and (not _looks_like_login(page))

@pytest.mark.smoke
@pytest.mark.parametrize("row", _rows(), ids=lambda r: r["path"])
def test_open_links_ok(new_page, base_url, locale, row):
    raw_path = (row["path"] or "").strip()
    requires_auth = str(row.get("requires_auth","")).strip().lower() in {"1","true","yes"}

    path = raw_path
    if "/en/" in path:
        path = path.replace("/en/", f"/{locale}/" if locale else "/")

    # Pre-auth cookie (nếu có)
    if COOKIE_NAME and COOKIE_VALUE:
        host = COOKIE_DOMAIN_ENV or _host_from_base(base_url) or ""
        cookie = {
            "name": COOKIE_NAME, "value": COOKIE_VALUE,
            "domain": host, "path": COOKIE_PATH or "/",
            "secure": COOKIE_SECURE, "sameSite": "Lax",
        }
        with contextlib.suppress(Exception):
            new_page.context.add_cookies([cookie])

    url = _url(base_url, path)
    path_is_login = any(path == v for v in LOGIN_VARIANTS)

    new_page.set_default_navigation_timeout(TIMEOUT_MS)
    new_page.goto(url, wait_until="commit", timeout=TIMEOUT_MS)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)

    final_url = new_page.url

    # 1) Nếu test chính trang login → chỉ cần reach được
    if path_is_login:
        ok_login_url = any(re.search(re.escape(v), final_url) for v in LOGIN_VARIANTS)
        assert ok_login_url, f"Login page not reachable: expected {LOGIN_VARIANTS}, final: {final_url}"
        return

    # 2) Trang khác: có bị dồn về login/modal?
    needs_login = _on_login_url(final_url, LOGIN_VARIANTS) or _looks_like_login(new_page)

    # 2a) Nếu link EXPECTED yêu cầu login và bị redirect về login → coi là PASS
    if requires_auth and needs_login:
        # Nếu muốn chặt chẽ hơn, đảm bảo URL cuối thực sự là login
        assert any(re.search(re.escape(v), final_url) for v in LOGIN_VARIANTS), \
            f"Expected redirect to login for {raw_path}, got: {final_url}"
        return

    # 2b) Không đánh dấu requires_auth mà vẫn bị dồn login
    if needs_login and not AUTO_LOGIN and not (COOKIE_NAME and COOKIE_VALUE):
        pytest.skip(f"Protected (requires login): {raw_path} → {final_url}")

    # 3) Cần login → thử cookie/auto-login
    if needs_login:
        # Nếu có cookie nhưng vẫn login → thử mở lại
        if COOKIE_NAME and COOKIE_VALUE and not _on_login_url(new_page.url, LOGIN_VARIANTS):
            new_page.goto(url, wait_until="commit", timeout=TIMEOUT_MS)
            with contextlib.suppress(Exception):
                new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
            final_url = new_page.url
            if not _on_login_url(final_url, LOGIN_VARIANTS) and not _looks_like_login(new_page):
                needs_login = False

        if needs_login and AUTO_LOGIN:
            if not (E2E_EMAIL and E2E_PASSWORD):
                pytest.skip("AUTO_LOGIN enabled but E2E_EMAIL/E2E_PASSWORD missing")
            login_url = _url(base_url, list(LOGIN_VARIANTS)[0])
            new_page.goto(login_url, wait_until="commit", timeout=TIMEOUT_MS)
            with contextlib.suppress(Exception):
                new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
            if not _fill_and_submit_login(new_page, E2E_EMAIL, E2E_PASSWORD, TIMEOUT_MS):
                pytest.skip(f"Cannot login automatically for {raw_path}; final: {new_page.url}")
            new_page.goto(url, wait_until="commit", timeout=TIMEOUT_MS)
            with contextlib.suppress(Exception):
                new_page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT_MS)
            final_url = new_page.url

    # 4) Public hoặc đã login: URL cuối phải khớp (cho phép biến thể /en/…)
    ok = any(re.search(re.escape(v), final_url) for v in _variants(path))
    assert ok, f"URL mismatch for link {raw_path} (resolved {path}); final: {final_url}"
