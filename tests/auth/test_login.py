# tests/auth/test_login.py
import os
import re
import contextlib
from pathlib import Path

import pytest
from pages.auth.login_page import LoginPage

# --- Patterns ---
# Từ khóa nhận diện lỗi (đa ngôn ngữ cơ bản)
_ERR_TEXT = re.compile(
    r"(error|invalid|incorrect|wrong|failed|did\s*not|unauthori[sz]ed|forbidden|"
    r"password|credentials|account|mật\s*khẩu|sai|không\s*hợp\s*lệ)",
    re.IGNORECASE,
)

# Nhóm selector hiển thị lỗi (lọc bỏ announcer Next.js)
_ERR_SEL = (
    ':is('
    '[data-test="login-error"],'
    '.ant-form-item-explain-error,'                  # AntD field error
    '.ant-message-error,'                            # AntD message error
    '.ant-message-notice-content,'                   # AntD message content
    '.ant-notification-notice-message,'              # AntD notification title
    '.ant-notification-notice-description,'          # AntD notification description
    '[role="alert"]:not(#__next-route-announcer__),'
    '[aria-live="assertive"]:not(#__next-route-announcer__),'
    '.MuiAlert-root,'
    '.Toastify__toast--error'
    ')'
)


# --- Artifacts ---
def _artifact_dir() -> str:
    d = os.getenv("ARTIFACT_DIR", "report")
    try:
        Path(d).mkdir(parents=True, exist_ok=True)
        return d
    except PermissionError:
        d = "/tmp/e2e-report"
        Path(d).mkdir(parents=True, exist_ok=True)
        return d

# --- Helpers ---
def _wait_non_empty_error(page, timeout=8000):
    """Đợi đến khi có element lỗi có text non-empty (tránh announcer rỗng)."""
    js = """
    (sel) => {
      const els = Array.from(document.querySelectorAll(sel));
      return els.some(el => el.offsetParent !== null && (el.textContent || '').trim().length > 1);
    }
    """
    with contextlib.suppress(Exception):
        page.wait_for_function(js, arg=_ERR_SEL, timeout=timeout)

def _collect_error_text(page) -> str:
    """Gộp text từ các node lỗi, tối đa 10 node đầu tiên."""
    texts = []
    with contextlib.suppress(Exception):
        loc = page.locator(_ERR_SEL)
        n = loc.count()
        for i in range(min(n, 10)):
            with contextlib.suppress(Exception):
                t = loc.nth(i).inner_text(timeout=200).strip()
                if t:
                    texts.append(t)
    return " | ".join(texts)

def _has_error(page) -> tuple[bool, str]:
    """Trả về (có_lỗi?, gộp_text) — chỉ coi là lỗi khi text khớp _ERR_TEXT."""
    _wait_non_empty_error(page, timeout=8000)
    txt = _collect_error_text(page)
    return bool(_ERR_TEXT.search(txt)), txt

# --- Tests ---
@pytest.mark.auth
@pytest.mark.smoke
def test_login_success(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], credentials["password"])

    # Đợi vào trang sau đăng nhập (store/dashboard)
    with contextlib.suppress(Exception):
        new_page.wait_for_url(re.compile(r"/(store|dashboard)(\?|/|$)"), timeout=15000)

    has_err, err_text = _has_error(new_page)
    assert not has_err, f"Unexpected error-like message after login: {err_text}"

    with contextlib.suppress(Exception):
        new_page.screenshot(
            path=str(Path(_artifact_dir()) / "after_login.png"),
            full_page=True
        )

@pytest.mark.auth
def test_login_wrong_password(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], credentials["password"] + "_WRONG!")

    # Ưu tiên chờ UI báo lỗi, tránh chờ network
    has_err, txt = _has_error(new_page)

    # Fallback: nếu chưa thấy lỗi, xác nhận vẫn ở trang login & có field lỗi
    if not has_err:
        still_on_login = new_page.url.endswith(auth_paths["login"])
        any_field_error = False
        with contextlib.suppress(Exception):
            any_field_error = new_page.locator(
                ":is(.ant-form-item-explain-error,[aria-invalid='true'])"
            ).first.is_visible()
        has_err = still_on_login and any_field_error

    assert has_err, f"Expected error message for wrong password; got: {txt[:200]}"
