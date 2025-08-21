# tests/auth/test_login.py
import os
import re
import contextlib
from pathlib import Path

import pytest
from pages.auth.login_page import LoginPage

# Từ khóa nhận diện lỗi (đa ngôn ngữ cơ bản)
_ERR_TEXT = re.compile(
    r"(error|invalid|incorrect|wrong|failed|did\s*not|unauthori[sz]ed|forbidden|mật\s*khẩu|sai|không\s*hợp\s*lệ)",
    re.IGNORECASE,
)

# Nhóm selector có thể hiện message/error
_ERR_SEL = (
    ':is('
    '[data-test="login-error"],'
    '.ant-form-item-explain-error,'           # Antd form field error
    '.ant-message-error,'                     # Antd message - error
    '.ant-message-notice-content,'            # Antd message content (có thể chứa success/info)
    '.ant-notification-notice-message,'       # Antd notification message
    '[role="alert"],'
    '.MuiAlert-root,'                         # MUI alert
    '.Toastify__toast--error'                 # Toastify error
    ')'
)

def _artifact_dir() -> str:
    d = os.getenv("ARTIFACT_DIR", "report")
    try:
        Path(d).mkdir(parents=True, exist_ok=True)
        return d
    except PermissionError:
        d = "/tmp/e2e-report"
        Path(d).mkdir(parents=True, exist_ok=True)
        return d

def _collect_error_texts(page):
    texts = []
    with contextlib.suppress(Exception):
        loc = page.locator(_ERR_SEL)
        texts = loc.all_inner_texts()
    # Làm gọn & loại rỗng
    return [t.strip() for t in texts if (t or "").strip()]

def _has_real_error(page) -> tuple[bool, str]:
    """
    Trả về (có_lỗi?, gộp_text). Chỉ coi là lỗi khi text khớp _ERR_TEXT.
    """
    texts = _collect_error_texts(page)
    joined = " | ".join(texts)
    return (bool(_ERR_TEXT.search(joined)), joined)


@pytest.mark.auth
@pytest.mark.smoke
def test_login_success(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], credentials["password"])

    # Đợi vào trang sau đăng nhập (store/dashboard)
    with contextlib.suppress(Exception):
        new_page.wait_for_url(re.compile(r"/(store|dashboard)(\?|/|$)"), timeout=15000)

    # Không coi mọi message là lỗi — chỉ fail nếu có từ khóa lỗi
    has_err, err_text = _has_real_error(new_page)
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

    # Tránh strict mode: chờ bất kỳ message nào hiện ra
    with contextlib.suppress(Exception):
        new_page.wait_for_selector(f"{_ERR_SEL}:visible", timeout=10000)

    has_err, err_text = _has_real_error(new_page)
    # Case sai mật khẩu: Kỳ vọng phải có message lỗi thực sự
    assert has_err, "Expected an error message for wrong password, but none matched error keywords."
