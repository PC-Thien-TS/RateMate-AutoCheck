# -*- coding: utf-8 -*-
import re
import pytest
from pages.auth.login_page import LoginPage

@pytest.mark.smoke
def test_language_switch_en_vi(new_page, base_url, auth_paths, locales):
    # Nếu site chưa bật tiếng Việt thì bỏ qua test này
    if "vi" not in [l.strip().lower() for l in locales]:
        pytest.skip("VI locale not configured")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto()

    # Mặc định English: có nút "Log in"
    assert new_page.get_by_role(
        "button", name=re.compile(r"Log\s*in", re.I)
    ).first.is_visible()

    # Chuyển sang Tiếng Việt và kiểm tra nút "Đăng nhập"
    lp.set_language("vi")
    assert new_page.get_by_role(
        "button", name=re.compile(r"Đăng\s*nhập", re.I)
    ).first.is_visible()
