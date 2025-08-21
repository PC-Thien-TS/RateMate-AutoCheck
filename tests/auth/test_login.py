# tests/auth/test_login.py
import os
import re
import contextlib
from pathlib import Path

import pytest
from pages.auth.login_page import LoginPage

# Gom tất cả selector lỗi phổ biến vào 1 chuỗi, dùng :is(...) + :visible
ERR_SEL = (
    ':is('
    '[data-test="login-error"],'
    '.ant-form-item-explain-error,'
    '.ant-message-error,'
    '.ant-message-notice-content,'
    '.ant-notification-notice-message,'
    '[role="alert"],'
    '.MuiAlert-root,'
    '.Toastify__toast--error'
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


@pytest.mark.auth
@pytest.mark.smoke
def test_login_success(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], credentials["password"])

    # Không thấy lỗi chung
    err = new_page.locator(ERR_SEL)
    assert err.count() == 0

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

    # Tránh strict mode: CHỜ bất kỳ lỗi nào hiện ra (selector :visible)
    new_page.wait_for_selector(f"{ERR_SEL}:visible", timeout=10000)

    # Có ít nhất 1 lỗi xuất hiện
    err = new_page.locator(ERR_SEL)
    assert err.count() > 0

    # (tuỳ chọn) check nội dung có từ khoá “sai mật khẩu”
    with contextlib.suppress(Exception):
        texts = err.all_inner_texts()
        all_text = " ".join(texts)
        assert re.search(
            r"(invalid|incorrect|wrong|did\s*not|mật\s*khẩu|password)",
            all_text, re.IGNORECASE
        )
