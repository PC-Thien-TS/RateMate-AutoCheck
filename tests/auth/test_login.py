# tests/auth/test_login.py
import os
import contextlib
from pathlib import Path
import pytest
from pages.auth.login_page import LoginPage

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
    err = new_page.locator('[data-test="login-error"]') \
        .or_(new_page.locator('.ant-form-item-explain-error')) \
        .or_(new_page.locator('.ant-message-error')) \
        .or_(new_page.locator('.ant-message-notice-content')) \
        .or_(new_page.locator('.ant-notification-notice-message'))
    assert err.count() == 0

    # Chụp ảnh về thư mục artifact (an toàn quyền ghi trong CI)
    with contextlib.suppress(Exception):
        new_page.screenshot(path=str(Path(_artifact_dir()) / "after_login.png"), full_page=True)

@pytest.mark.auth
def test_login_wrong_password(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], credentials["password"] + "_WRONG!")
    err = new_page.locator('[data-test="login-error"]') \
        .or_(new_page.locator('.ant-form-item-explain-error')) \
        .or_(new_page.locator('.ant-message-error')) \
        .or_(new_page.locator('.ant-message-notice-content')) \
        .or_(new_page.locator('.ant-notification-notice-message'))
    err.wait_for(state="visible", timeout=10000)
    assert err.count() > 0
