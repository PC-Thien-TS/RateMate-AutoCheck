import re
import pytest
from pages.auth.login_page import LoginPage

@pytest.mark.auth
@pytest.mark.smoke
def test_login_success(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], credentials["password"])

    # Không thấy lỗi chung
    error_banner = new_page.locator(
        '[data-test="login-error"]'
    ).or_(new_page.locator('.ant-form-item-explain-error')
    ).or_(new_page.locator('.ant-message-error')
    ).or_(new_page.locator('.ant-message-notice-content')
    ).or_(new_page.locator('.ant-notification-notice-message'))
    assert error_banner.count() == 0
    new_page.screenshot(path="report/after_login.png", full_page=True)

@pytest.mark.auth
def test_login_wrong_password(new_page, base_url, auth_paths, credentials):
    login = LoginPage(new_page, base_url, auth_paths["login"])
    login.goto()
    login.login(credentials["email"], "WRONG_PASS_123")

    # Hợp nhất nhiều locator lỗi (AntD + regex text)
    candidates = (
        new_page.locator('[data-test="login-error"]')
        .or_(new_page.locator('.ant-form-item-explain-error'))
        .or_(new_page.locator('.ant-message-error'))
        .or_(new_page.locator('.ant-message-notice-content'))
        .or_(new_page.locator('.ant-notification-notice-message'))
        .or_(new_page.locator('div[role="alert"]'))
        .or_(new_page.get_by_text(re.compile(r'(invalid|incorrect|failed|wrong|sai mật khẩu|không đúng)', re.I)))
    )
    # Đợi tối đa 7s cho lỗi xuất hiện
    candidates.first.wait_for(state="visible", timeout=7000)
