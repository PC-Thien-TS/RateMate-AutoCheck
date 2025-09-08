# pages/auth/login_page.py
import re
import contextlib
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, Locator

# -------------------- helpers --------------------

@dataclass
class ResponseLike:
    status: Optional[int] = None
    url: Optional[str] = None
    body: str = ""


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


def _is_inside_ion_searchbar(loc: Locator) -> bool:
    try:
        anc = loc.locator("xpath=ancestor::ion-searchbar[1]")
        return anc.count() > 0
    except Exception:
        return False


def _first_visible(loc: Locator, timeout_ms: int = 6000) -> Optional[Locator]:
    try:
        item = loc.first
        item.wait_for(state="visible", timeout=timeout_ms)
        return item
    except Exception:
        return None


def _class_contains_expr(s: str) -> str:
    s = s.lower()
    return "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'%s')" % s


# -------------------- Login Page --------------------

class LoginPage:
    def __init__(self, page: Page, base_url: str, login_path: str = "/login"):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.login_path = login_path if login_path.startswith("/") else f"/{login_path}"

    def _candidate_paths(self):
        seen = set()
        order = [
            self.login_path,
            "/login", "/log-in", "/signin", "/sign-in",
            "/auth/login",
        ]
        for p in order:
            if p and p not in seen:
                seen.add(p)
                yield p

    def goto(self):
        last_err = None
        for p in self._candidate_paths():
            url = f"{self.base_url}{p}"
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=12_000)
                with contextlib.suppress(Exception):
                    self.page.wait_for_timeout(250)
                if re.search(r"/(auth/login|log[-_]?in|sign[-_]?in)(\?|/|$)", self.page.url, re.I):
                    return
            except Exception as e:
                last_err = e
        if last_err:
            raise last_err

    # ----- chuyển qua chế độ password (nếu có) -----
    def _switch_to_password_mode(self):
        with contextlib.suppress(Exception):
            tab = self.page.get_by_role("tab", name=re.compile(r"(password|mật\s*khẩu)", re.I)).first
            tab.wait_for(state="visible", timeout=800)
            tab.click(timeout=800)
            self.page.wait_for_timeout(150)

        with contextlib.suppress(Exception):
            btn = self.page.get_by_role(
                "button",
                name=re.compile(r"(email\s*&\s*password|mật\s*khẩu|use\s*password)", re.I),
            ).first
            btn.wait_for(state="visible", timeout=800)
            btn.click(timeout=800)
            self.page.wait_for_timeout(150)

    # ----- scope tìm container của form/auth -----
    def _find_form_scope(self, anchor: Optional[Locator]) -> Optional[Locator]:
        if not anchor:
            return None
        with contextlib.suppress(Exception):
            f = anchor.locator("xpath=ancestor::form[1]")
            if f.count() > 0:
                return f.first
        with contextlib.suppress(Exception):
            f = anchor.locator("xpath=ancestor::*[@role='form' or contains(@class,'form')][1]")
            if f.count() > 0:
                return f.first
        with contextlib.suppress(Exception):
            xpath = (
                "xpath=ancestor::*["
                f"{_class_contains_expr('login')} or "
                f"{_class_contains_expr('auth')} or "
                f"{_class_contains_expr('sign')}"
                "][1]"
            )
            f = anchor.locator(xpath)
            if f.count() > 0:
                return f.first
        return None

    # ----- field locators (ưu tiên container, tránh ion-searchbar) -----

    def _email_input(self) -> Locator:
        forms = self.page.locator("form")
        try:
            cnt = min(forms.count(), 4)
        except Exception:
            cnt = 0

        # 1) Form hiện tại (trước)
        for i in range(cnt):
            f = forms.nth(i)
            cand = f.locator(
                "input[type='email'], "
                "input[autocomplete*='username' i], "
                "input[name*='email' i], input[id*='email' i], "
                "input[name*='user' i], input[id*='user' i]"
            )
            el = _first_visible(cand, timeout_ms=3500)
            if el and not _is_inside_ion_searchbar(el):
                return el

        # 2) Thử bật password-mode rồi tìm lại
        self._switch_to_password_mode()
        for i in range(cnt):
            f = forms.nth(i)
            cand = f.locator(
                "input[type='email'], "
                "input[autocomplete*='username' i], "
                "input[name*='email' i], input[id*='email' i], "
                "input[name*='user' i], input[id*='user' i]"
            )
            el = _first_visible(cand, timeout_ms=2500)
            if el and not _is_inside_ion_searchbar(el):
                return el

        # 3) Nếu có password thì tìm input “anh/chị em” trong container
        pwd = None
        with contextlib.suppress(Exception):
            pwd = self._password_input()
        scope = self._find_form_scope(pwd) if pwd else None
        if scope is None:
            scope = self.page

        if pwd:
            near_pwd = pwd.locator(
                "xpath=ancestor::*[self::form or "
                "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login') or "
                "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'auth') or "
                "contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign')][1]"
                "//input[not(@type='password') and not(@type='search')]"
            )
            try:
                ncnt = min(near_pwd.count(), 6)
            except Exception:
                ncnt = 0
            for i in range(ncnt):
                cand = near_pwd.nth(i)
                try:
                    cand.wait_for(state="visible", timeout=1200)
                    if _is_inside_ion_searchbar(cand):
                        continue
                    with contextlib.suppress(Exception):
                        ph = (cand.get_attribute("placeholder") or "").strip()
                    with contextlib.suppress(Exception):
                        nm = (cand.get_attribute("name") or "") + " " + (cand.get_attribute("id") or "")
                    if re.search(r"(e-?mail|email|username|user\s*name|phone|mobile|điện\s*thoại|tài\s*khoản)", ph + " " + nm, re.I):
                        return cand
                except Exception:
                    continue

        # 4) Fallback: label/placeholder/role textbox
        cand = self.page.get_by_label(
            re.compile(r"(e-?mail|email|username|user\s*name|phone|mobile|điện\s*thoại)", re.I)
        ).or_(
            self.page.get_by_placeholder(
                re.compile(r"(e-?mail|email|username|user\s*name|phone|mobile|điện\s*thoại)", re.I)
            )
        ).or_(
            self.page.get_by_role("textbox", name=re.compile(r"(e-?mail|email|username|user\s*name|phone|mobile|điện\s*thoại)", re.I))
        )
        el = _first_visible(cand, timeout_ms=2000)
        if el and not _is_inside_ion_searchbar(el):
            return el

        # 5) Fallback cuối: quét input toàn trang (loại password/search và ion-searchbar)
        generic = scope.locator("input:not([type='password']):not([type='search'])")
        try:
            gcnt = min(generic.count(), 10)
        except Exception:
            gcnt = 0
        for i in range(gcnt):
            cand = generic.nth(i)
            try:
                cand.wait_for(state="visible", timeout=1000)
                if _is_inside_ion_searchbar(cand):
                    continue
                with contextlib.suppress(Exception):
                    ph = (cand.get_attribute("placeholder") or "").strip()
                with contextlib.suppress(Exception):
                    nm = (cand.get_attribute("name") or "") + " " + (cand.get_attribute("id") or "")
                if re.search(r"(e-?mail|email|username|user\s*name|phone|mobile|điện\s*thoại|tài\s*khoản)", ph + " " + nm, re.I):
                    return cand
            except Exception:
                continue

        # Trả về locator hợp lệ để test fail hợp lý nếu nhập sai trường
        return generic.first

    def _reveal_password_if_needed(self):
        with contextlib.suppress(Exception):
            toggler = self.page.get_by_role(
                "button", name=re.compile(r"(show|hiện|toggle).*password", re.I)
            ).first
            toggler.wait_for(state="visible", timeout=800)
            toggler.click(timeout=800)

    def _password_input(self) -> Locator:
        self._reveal_password_if_needed()

        rx = re.compile(r"(password|mật\s*khẩu)", re.I)
        cand0 = self.page.get_by_label(rx).or_(
            self.page.get_by_placeholder(rx)
        ).or_(
            self.page.get_by_role("textbox", name=rx)
        )
        el0 = _first_visible(cand0, timeout_ms=2000)
        if el0 and not _is_inside_ion_searchbar(el0):
            return el0

        forms = self.page.locator("form")
        try:
            cnt = min(forms.count(), 4)
        except Exception:
            cnt = 0
        for i in range(cnt):
            f = forms.nth(i)
            cand = f.locator("input[type='password'], input[id*='pass' i], input[name*='pass' i]")
            el = _first_visible(cand, timeout_ms=3000)
            if el and not _is_inside_ion_searchbar(el):
                return el

        cand = self.page.locator(
            "input[type='password'], "
            "input[id*='pass' i], input[name*='pass' i], "
            "input[autocomplete*='current-password' i], input[autocomplete*='password' i]"
        )
        el = _first_visible(cand, timeout_ms=3000)
        if el and not _is_inside_ion_searchbar(el):
            return el

        cand2 = self.page.locator("input[placeholder*='password' i], input[placeholder*='mật' i]")
        el2 = _first_visible(cand2, timeout_ms=2000)
        if el2 and not _is_inside_ion_searchbar(el2):
            return el2

        # fallback cuối cùng
        try:
            return cand2.first if cand2.count() else cand.first
        except Exception:
            return self.page.locator("input").first

    # ----- submit -----

    def _submit_union(self, scope: Locator) -> Locator:
        by_role = scope.get_by_role(
            "button",
            name=re.compile(r"(đăng\s*nhập|login|log\s*in|sign\s*in|continue|tiếp)", re.I),
        )
        css_submit = scope.locator("button[type='submit'], input[type='submit']")
        css_named = scope.locator(
            "button:has-text('Đăng nhập'), button:has-text('Login'), "
            "button:has-text('Log in'), button:has-text('Sign in')"
        )
        cand = by_role.or_(css_submit).or_(css_named)
        # tránh nút reset/clear của ion-searchbar
        return cand.filter(has_not=self.page.locator("[aria-label='reset']")).locator(":not(ion-searchbar *)")

    def _pick_submit(
        self,
        form_scope: Optional[Locator],
        email_input: Optional[Locator],
        pwd: Optional[Locator],
    ) -> Optional[Locator]:
        for scope in (form_scope, self._find_form_scope(email_input) if email_input else None,
                      self._find_form_scope(pwd) if pwd else None, self.page):
            if scope is None:
                continue
            btn = _first_visible(self._submit_union(scope), timeout_ms=6_000)
            if btn:
                return btn
        return None

    # ----- actions -----

    def login(self, email: str, password: str, wait_response_ms: int = 15_000) -> ResponseLike:
        self._switch_to_password_mode()

        email_input = self._email_input()
        _fill_force(email_input, email)

        pwd = self._password_input()
        _fill_force(pwd, password)

        form_scope = self._find_form_scope(email_input) or self._find_form_scope(pwd) or self.page

        with contextlib.suppress(Exception):
            btn = self._pick_submit(form_scope, email_input, pwd)
            if btn:
                btn.click(timeout=2_500)

        patt = re.compile(r"/(auth|login|log[-_]?in|sign|session|token)", re.I)
        status = None
        url = self.page.url
        body = ""
        with contextlib.suppress(Exception):
            resp = self.page.wait_for_response(
                lambda r: (patt.search(r.url or "") is not None)
                or (getattr(r, "request", None) and r.request.method in ("POST", "PUT", "PATCH") and patt.search(r.url or "")),
                timeout=wait_response_ms,
            )
            with contextlib.suppress(Exception):
                status = resp.status if hasattr(resp, "status") else resp.status()
            with contextlib.suppress(Exception):
                url = resp.url
            with contextlib.suppress(Exception):
                body = resp.text() or ""

        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("domcontentloaded", timeout=5_000)

        return ResponseLike(status=status, url=url, body=body)
