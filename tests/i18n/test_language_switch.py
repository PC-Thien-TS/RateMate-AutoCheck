import os
import pytest

if 'vi' not in os.getenv('LOCALES','en').split(','):
    pytest.skip('VI locale not available externally; skip i18n switch', allow_module_level=True)

import re
from pages.auth.login_page import LoginPage
import pytest

@pytest.mark.smoke
def test_language_switch_en_vi(new_page, base_url, auth_paths):
    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto()
    # mặc định English có nút Log in
    assert new_page.get_by_role("button", name=re.compile("Log\\s*in", re.I)).first.is_visible()
    # chuyển Tiếng Việt
    lp.set_language("vi")
    assert new_page.get_by_role("button", name=re.compile("Đăng\\s*nhập", re.I)).first.is_visible()
