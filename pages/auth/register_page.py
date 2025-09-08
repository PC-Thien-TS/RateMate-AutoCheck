# pages/auth/register_page.py
from __future__ import annotations
import re
import time
import contextlib
from typing import Optional
from playwright.sync_api import Page, Locator


class ResponseLike:
    def __init__(self, status=None, url="", body=""):
        self.status = status
        self.url = url
        self._body = body

    def text(self) -> str:
        return self._body or ""


# ---------- helpers ----------

def _is_inside_ion_searchbar(loc: Locator) -> bool:
    try:
        anc = loc.locator("xpath=ancestor::ion-searchbar[1]")
        return anc.count() > 0
    except Exception:
        return False


def _fill_force(locator: Locator, value, timeout: int = 10_000):
    """
    Điền giá trị vào input ổn định:
    - Ưu tiên .fill() (nhanh, ít rủi ro)
    - Nếu lỗi (DOM đặc thù), fallback JS set value + dispatch sự kiện
    """
    locator.wait_for(state="visible", timeout=timeout)
    try:
        locator.click()
        locator.fill("")  # clear
        locator.fill(str(value), timeout=timeout)
    except Exception:
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


def _pick_visible(raw: Locator, timeout_ms: int = 8000) -> Locator:
    """
    Chọn phần tử đầu tiên "visible" trong nhóm. Đợi tối đa timeout_ms.
    Bỏ qua node nằm trong ion-searchbar.
    """
    deadline = time.time() + timeout_ms / 1000.0
    last_first = raw.first
    while time.time() < deadline:
        try:
            n = min(raw.count(), 12)
        except Exception:
            n = 0
        for i in range(n):
            el = raw.nth(i)
            try:
                el.wait_for(state="visible", timeout=400)
                if not _is_inside_ion_searchbar(el):
                    return el
            except Exception:
                continue
        # backoff ngắn rồi thử lại
        try:
            raw.page.wait_for_timeout(120)
        except Exception:
            pass
    return last_first


def _input_union(scope: Locator, patterns: str) -> Locator:
    """
    Gom ứng viên input theo label / placeholder / role / input thường.
    """
    rx = re.compile(patterns, re.IGNORECASE)
    return scope.get_by_label(rx).or_(
        scope.get_by_placeholder(rx)
    ).or_(
        scope.get_by_role("textbox", name=rx)
    ).or_(
        scope.locator("input, textarea, [contenteditable], [contenteditable='true']")
    )


# ---------- Page Object ----------

class RegisterPage:
    def __init__(self, page: Page, base_url: str, path: str):
        self.page = page
        self.base_url = (base_url or "").rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"

    def goto(self):
        self.page.goto(f"{self.base_url}{self.path}", wait_until="domcontentloaded")

    def _open_register_ui(self):
        with contextlib.suppress(Exception):
            tab = self.page.get_by_role("tab", name=_REGISTER_TAB_PATTERN)
            if tab.count() > 0:
                t = tab.first
                t.wait_for(state="visible", timeout=800)
                t.click(timeout=800)
                self.page.wait_for_timeout(150)

        with contextlib.suppress(Exception):
            btn = self.page.get_by_role("button", name=_REGISTER_BTN_PATTERN)
            if btn.count() > 0:
                b = btn.first
                b.wait_for(state="visible", timeout=800)
                b.click(timeout=800)
                self.page.wait_for_timeout(150)

    # ----- field fills -----

    def _fill_email(self, email: str):
        # ưu tiên email/username/phone
        loc = _input_union(self.page, _EMAIL_PATTERN.pattern)
        el = _pick_visible(loc, timeout_ms=5000)
        _fill_force(el, email)

    def _fill_full_name(self, name: str):
        loc = _input_union(self.page, _FULL_NAME_PATTERN.pattern)
        el = _pick_visible(loc, timeout_ms=4000)
        with contextlib.suppress(Exception):
            _fill_force(el, name)

    def _fill_password(self, pw: str):
        # gồm cả placeholder 'password' dù type không hẳn password
        loc = self.page.get_by_label(_PASSWORD_PATTERN).or_(
            self.page.get_by_placeholder(_PASSWORD_PATTERN)
        ).or_(
            self.page.locator(
                "input[type='password'], "
                "input[id*='pass' i], input[name*='pass' i], "
                "input[autocomplete*='current-password' i], input[autocomplete*='password' i]"
            )
        )
        el = _pick_visible(loc, timeout_ms=5000)
        _fill_force(el, pw)

    def _fill_confirm(self, pw: str):
        # confirm/verify/retype
        loc = _input_union(self.page, _CONFIRM_PW_PATTERN.pattern)
        el = _pick_visible(loc, timeout_ms=4000)
        with contextlib.suppress(Exception):
            _fill_force(el, pw)

    def _click_submit(self):
        cand = self.page.get_by_role("button", name=_SUBMIT_BTN_PATTERN).or_(
            self.page.locator("button[type='submit'], input[type='submit']")
        )
        btn = _pick_visible(cand, timeout_ms=5000)
        with contextlib.suppress(Exception):
            btn.wait_for(state="attached", timeout=600)
            btn.click(timeout=3000)

    # ----- feedback -----

    def visible_error_text(self, timeout: int = 5000) -> str:
        end = time.time() + timeout / 1000.0
        loc = self.page.locator(_ERROR_SELECTOR)
        while time.time() < end:
            with contextlib.suppress(Exception):
                if loc.count() > 0:
                    el = loc.first
                    el.wait_for(state="visible", timeout=400)
                    t = (el.inner_text(timeout=300) or "").strip()
                    if t:
                        return t
            self.page.wait_for_timeout(120)
        return ""

    # ----- main action -----

    def register_email(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        confirm_password: Optional[str] = None,
        wait_response_ms: int = 12_000,
    ) -> ResponseLike:
        self._open_register_ui()
        if full_name:
            self._fill_full_name(full_name)
        self._fill_email(email)
        self._fill_password(password)
        # nếu confirm field không tồn tại thì _pick_visible sẽ trả về first hợp lệ; try/except để không crash
        with contextlib.suppress(Exception):
            self._fill_confirm(confirm_password or password)

        # chờ response POST/PUT/PATCH tới endpoint liên quan register
        status, url, body = None, self.page.url, ""
        with contextlib.suppress(Exception):
            with self.page.expect_response(
                lambda r: r.request
                and r.request.method in ("POST", "PUT", "PATCH")
                and _REGISTER_API_PATTERN.search(r.url or ""),
                timeout=wait_response_ms,
            ) as resp_ctx:
                self._click_submit()
            r = resp_ctx.value
            with contextlib.suppress(Exception):
                status = r.status if hasattr(r, "status") else r.status()
            with contextlib.suppress(Exception):
                url = r.url
            with contextlib.suppress(Exception):
                body = r.text() or ""

        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("domcontentloaded", timeout=5_000)

        return ResponseLike(status=status, url=url, body=body)
