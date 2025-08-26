# pages/auth/login_page.py
from __future__ import annotations

import re
import time
import contextlib
from typing import Optional, Union
from playwright.sync_api import Page, Locator

# ----------------- small response wrapper -----------------
class ResponseLike:
    def __init__(self, status: Optional[int] = None, url: str = "", body: str = ""):
        self._status = status
        self.url = url
        self._body = body

    @property
    def status(self) -> Optional[int]:
        return self._status

    def text(self) -> str:
        return self._body or ""

# ----------------- helpers -----------------
def _as_fillable(loc: Locator) -> Locator:
    inner = loc.locator(
        "css=:scope >>> input, "
        ":scope >>> textarea, "
        ":scope >>> .native-input, "
        ":scope >>> [part='native'], "
        ":scope >>> [contenteditable], "
        ":scope >>> [contenteditable='true']"
    )
    if inner.count() > 0:
        return inner.first
    inner2 = loc.locator("css=input, textarea, [contenteditable], [contenteditable='true']")
    if inner2.count() > 0:
        return inner2.first
    return loc

def _scan_visible_editable(raw: Locator, page: Page, timeout_ms: int = 12000, scan_limit: int = 12) -> Optional[Locator]:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        try:
            n = raw.count()
        except Exception:
            n = 0
        if n > 0:
            upto = min(n, scan_limit)
            for i in range(upto):
                el = raw.nth(i)
                try:
                    if el.is_visible() and el.is_enabled() and el.is_editable():
                        return el
                except Exception:
                    pass
        page.wait_for_timeout(150)
    return None

def _pick_visible(raw: Locator, page: Page, timeout_ms: int = 9000, scan_limit: int = 12) -> Locator:
    deadline = time.time() + timeout_ms / 1000.0
    last_n = 0
    while time.time() < deadline:
        try:
            n = raw.count()
            last_n = n
        except Exception:
            n = 0
        if n > 0:
            upto = min(n, scan_limit)
            for i in range(upto):
                el = raw.nth(i)
                try:
                    if el.is_visible():
                        return el
                except Exception:
                    pass
        page.wait_for_timeout(150)
    return raw.first if last_n > 0 else raw

def _fill_any(page: Page, loc: Locator, value: str) -> None:
    loc = _as_fillable(loc)
    for fn, arg in (("click", None), ("fill", ""), ("fill", value), ("type", value)):
        try:
            getattr(loc, fn)(*((),)[0] if arg is None else (arg,), timeout=2000)
            if fn in ("fill", "type") and arg == value:
                return
        except Exception:
            pass
    try:
        handle = loc.element_handle(timeout=1500)
        if handle:
            page.evaluate(
                "(el, v) => { if ('value' in el) { el.value = v; } "
                "el.dispatchEvent(new Event('input', {bubbles:true})); "
                "el.dispatchEvent(new Event('change', {bubbles:true})); }",
                handle, value
            )
    except Exception:
        pass

def _textbox_union(scope: Union[Page, Locator], patterns: str) -> Locator:
    by_label = scope.get_by_label(re.compile(patterns, re.IGNORECASE))
    by_placeholder = scope.get_by_placeholder(re.compile(patterns, re.IGNORECASE))
    by_role = scope.get_by_role("textbox", name=re.compile(patterns, re.IGNORECASE))
    by_testid = scope.get_by_test_id(re.compile(patterns, re.IGNORECASE))
    css_plain = scope.locator(
        "css=input[type='text'], input[type='email'], textarea, "
        "input[id*='email' i], input[name*='email' i], "
        "input[id*='user' i], input[name*='user' i], "
        "input[id*='identifier' i], input[name*='identifier' i], "
        "input[id*='login' i], input[name*='login' i], "
        "input[id*='phone' i], input[name*='phone' i], "
        "[contenteditable], [contenteditable='true']"
    )
    css_ionic = scope.locator("css=ion-input, ion-textarea, ion-item input, ion-item textarea")
    return by_label.or_(by_placeholder).or_(by_role).or_(by_testid).or_(css_plain).or_(css_ionic)

def _password_union(scope: Union[Page, Locator]) -> Locator:
    patt = r"(mật\s*khẩu|password|pass|pwd)"
    by_label = scope.get_by_label(re.compile(patt, re.IGNORECASE))
    by_placeholder = scope.get_by_placeholder(re.compile(patt, re.IGNORECASE))
    css_plain = scope.locator(
        "css=input[type='password'], "
        "input[id*='pass' i], input[name*='pass' i], "
        "input[autocomplete*='current-password' i], input[autocomplete*='password' i]"
    )
    css_ionic = scope.locator("css=ion-input, ion-textarea")
    return by_label.or_(by_placeholder).or_(css_plain).or_(css_ionic)

def _submit_union(scope: Union[Page, Locator]) -> Locator:
    # Loại trừ GSI/Google buttons
    gsi = scope.locator("[id^='gsi_'], iframe[src*='accounts.google'], [aria-label*='Google i']", has_text=re.compile("Google", re.I))
    by_role = scope.get_by_role("button", name=re.compile(r"(đăng\s*nhập|login|sign\s*in)", re.IGNORECASE))
    css_plain = scope.locator("css=button[type='submit'], form button.ant-btn[type='submit'], form [type='submit']")
    submit = by_role.or_(css_plain)
    try:
        submit = submit.filter(has_not=gsi)
    except Exception:
        pass
    return submit

def _error_union(scope: Union[Page, Locator]) -> Locator:
    """
    Selector bắt thông điệp lỗi theo nhiều UI lib.
    Tránh ::part/>>> ở selector lỗi để an toàn multi-engine.
    """
    groups = [
        # tiêu chuẩn/aria/generic (loại announcer Next.js)
        "[role='alert']:not(#__next-route-announcer__), [aria-live='assertive']:not(#__next-route-announcer__)",
        ".invalid-feedback, .form-error",
        ".error, .error-message, .text-danger, .text-red-500, .text-red-600",
        "span.help-block, .help.is-danger",
        # Ant Design / notifications
        ".ant-form-item-explain-error, .ant-alert-message, .ant-message-notice .ant-message-custom-content, .ant-notification-notice-description, .ant-notification-notice-message",
        # Material / Chakra / MUI / Prime / others
        "mat-error, .mat-mdc-form-field-error, .MuiAlert-message, .chakra-alert, .p-message .p-message-text, .v-alert__content, .el-message__content",
        # Toast / Notification phổ biến
        ".toast-message, .notification-message",
        # Ionic (phát hiện component)
        "ion-note[color='danger'], ion-text[color='danger'], ion-toast, ion-alert",
    ]
    loc = scope.locator("css=" + groups[0])
    for g in groups[1:]:
        loc = loc.or_(scope.locator("css=" + g))
    return loc

def _fallback_any_textbox(scope: Union[Page, Locator], page: Page) -> Locator:
    ionic_inner = scope.locator("css=ion-input >>> input, ion-textarea >>> textarea, ion-item input, ion-item textarea")
    el = _scan_visible_editable(ionic_inner, page, timeout_ms=5000)
    if el:
        return _as_fillable(el)
    ionic_any = scope.locator("css=ion-input, ion-textarea")
    el2 = _scan_visible_editable(ionic_any, page, timeout_ms=4000)
    if el2:
        return _as_fillable(el2)
    broad = scope.locator(
        "css=input:not([type='hidden']):not([type='checkbox']):not([type='radio']):"
        "not([type='file']):not([type='submit']), "
        "textarea, [contenteditable], [contenteditable='true']"
    )
    el3 = _scan_visible_editable(broad, page, timeout_ms=4000)
    if el3:
        return _as_fillable(el3)
    return scope.locator("css=input, textarea, [contenteditable], [contenteditable='true']").first

# ----------------- Page object -----------------
class LoginPage:
    def __init__(self, page: Page, base_url: str, path: str):
        self.page = page
        self.base_url = (base_url or "").rstrip("/")
        self.path = path if path.startswith("/") else f"/{path}"

    def _candidate_paths(self) -> list[str]:
        uniq = []
        for p in [self.path, "/login", "/sign-in", "/signin", "/auth/login"]:
            if p not in uniq:
                uniq.append(p)
        return uniq

    def goto(self) -> None:
        for p in self._candidate_paths():
            try:
                self.page.goto(f"{self.base_url}{p}", wait_until="domcontentloaded")
                container = self.page.locator("form, ion-content, ion-card, .ant-form, [role='form']")
                if container.count() > 0:
                    self.page.wait_for_timeout(300)
                    return
            except Exception:
                continue
        self.page.wait_for_timeout(150)

    # ---------- locators ----------
    def _email_input(self) -> Locator:
        patterns = r"(e-?mail|email|username|user\s*name|tên\s*đăng\s*nhập|phone|số\s*điện\s*thoại|sdt|mobile)"
        raw = _textbox_union(self.page, patterns).or_(
            self.page.locator("css=ion-input[name*='email' i], ion-input[type='email'], input[name*='email' i], input[type='email']")
        )
        el = _scan_visible_editable(raw, self.page, timeout_ms=9000)
        return _as_fillable(el) if el else _fallback_any_textbox(self.page, self.page)

    def _password_input(self) -> Locator:
        raw = _password_union(self.page).or_(
            self.page.locator("css=ion-input[type='password'], input[type='password'], ion-input[name*='pass' i], input[name*='pass' i]")
        )
        el = _scan_visible_editable(raw, self.page, timeout_ms=9000)
        return _as_fillable(el) if el else _fallback_any_textbox(self.page, self.page)

    def _submit(self) -> Locator:
        # Ưu tiên nút submit trong form nếu có
        form = self.page.locator("form").first
        if form.count() > 0:
            cand = _submit_union(form)
            btn = _pick_visible(cand, self.page, timeout_ms=6000)
            if btn:
                return btn
        return _pick_visible(_submit_union(self.page), self.page, timeout_ms=12000)

    # ---------- error helpers ----------
    def visible_error_locator(self) -> Locator:
        union = _error_union(self.page)
        try:
            vis = union.filter(has_text=re.compile(r".+")).first
            if vis and vis.count() > 0:
                return vis
        except Exception:
            pass
        return union

    def error_text(self, timeout_ms: int = 4000) -> str:
        loc = self.visible_error_locator()
        deadline = time.time() + timeout_ms / 1000.0
        while time.time() < deadline:
            try:
                if loc.count() > 0 and loc.first.is_visible():
                    t = (loc.first.inner_text(timeout=500) or "").strip()
                    if t:
                        return t
            except Exception:
                pass
            self.page.wait_for_timeout(150)
        return ""

    def visible_error_text(self, timeout: int = 4000) -> str:  # Back-compat alias
        return self.error_text(timeout_ms=timeout)

    # ---------- actions ----------
    def login(self, email: str, password: str, wait_response_ms: int = 6000) -> ResponseLike:
        _fill_any(self.page, self._email_input(), email)
        _fill_any(self.page, self._password_input(), password)

        try:
            self._submit().click(timeout=3000)
        except Exception:
            try:
                _as_fillable(self._password_input()).press("Enter", timeout=1500)
            except Exception:
                pass

        self.page.wait_for_timeout(400)

        patt = re.compile(r"/(auth|login|sign|session)", re.IGNORECASE)
        status: Optional[int] = None
        url: str = ""
        body: str = ""
        try:
            resp = self.page.wait_for_response(lambda r: bool(patt.search(r.url or "")), timeout=wait_response_ms)
            try:
                status = resp.status
            except Exception:
                try:
                    status = resp.status()
                except Exception:
                    status = None
            url = resp.url
            try:
                body = resp.text()
            except Exception:
                body = url
        except Exception:
            url = self.page.url

        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)

        return ResponseLike(status=status, url=url, body=body)
