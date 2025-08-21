import os
from pathlib import Path
import pytest
from pages.auth.login_page import LoginPage


def _ensure_artifact_dir() -> str:
    # Ưu tiên đường dẫn từ env (CI mount vào /out)
    d = os.getenv("ARTIFACT_DIR", "report")
    try:
        Path(d).mkdir(parents=True, exist_ok=True)
        return d
    except PermissionError:
        # Fallback nếu bind mount /app chỉ đọc
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
    error_banner = new_page.locator('[data-test="login-error"]') \
        .or_(new_page.locator('.ant-form-item-explain-error')) \
        .or_(new_page.locator('.ant-message-error')) \
        .or_(new_page.locator('.ant-message-notice-content')) \
        .or_(new_page.locator('.ant-notification-notice-message'))
    assert error_banner.count() == 0

    # Chụp screenshot sau login vào thư mục artifact an toàn
    report_dir = _ensure_artifact_dir()
    new_page.screenshot(path=str(Path(report_dir) / "after_login.png"), full_page=True)


@pytest.mark.auth
def test_login_wrong_password(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], "this-is-wrong-password")

    error_banner = new_page.locator('[data-test="login-error"]') \
        .or_(new_page.locator('.ant-form-item-explain-error')) \
        .or_(new_page.locator('.ant-message-error')) \
        .or_(new_page.locator('.ant-message-notice-content')) \
        .or_(new_page.locator('.ant-notification-notice-message'))

    assert error_banner.count() > 0
