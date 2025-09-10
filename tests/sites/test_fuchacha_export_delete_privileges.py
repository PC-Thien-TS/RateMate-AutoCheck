# -*- coding: utf-8 -*-
import os
import re
import contextlib
import pytest
pytestmark = [pytest.mark.roles]

from pages.auth.login_page import LoginPage


def _open_system_manage(new_page, base_url: str):
    new_page.goto(f"{base_url.rstrip('/')}/system-manage/user-manage", wait_until="domcontentloaded")
    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(300)


@pytest.mark.smoke
def test_export_requires_password_platform_admin(new_page, site, base_url, auth_paths, platform_admin_credentials):
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")
    if not (platform_admin_credentials.get("email") and platform_admin_credentials.get("password")):
        pytest.skip("Missing platform admin credentials")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto(); lp.login(platform_admin_credentials["email"], platform_admin_credentials["password"]) 
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)

    _open_system_manage(new_page, base_url)

    # Find Export button and click
    export_clicked = False
    for patt in (r"Export|Xuất|导出"):
        with contextlib.suppress(Exception):
            btn = new_page.get_by_role("button", name=re.compile(patt, re.I)).first
            if btn and btn.is_visible():
                btn.click(); export_clicked = True; break
    if not export_clicked:
        pytest.skip("Export control not found for platform admin")

    # Expect password prompt
    prompted = False
    with contextlib.suppress(Exception):
        prompted = new_page.get_by_label(re.compile(r"password|mật\s*khẩu|密码", re.I)).first.is_visible(timeout=1200)
    if not prompted:
        with contextlib.suppress(Exception):
            prompted = new_page.get_by_placeholder(re.compile(r"password|mật\s*khẩu|密码", re.I)).first.is_visible(timeout=1200)
    assert prompted, "Export should require a password prompt"


@pytest.mark.smoke
def test_delete_all_visible_only_to_platform_admin(new_page, site, base_url, auth_paths, super_admin_credentials):
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")
    if not (super_admin_credentials.get("email") and super_admin_credentials.get("password")):
        pytest.skip("Missing super admin credentials")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto(); lp.login(super_admin_credentials["email"], super_admin_credentials["password"]) 
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)

    _open_system_manage(new_page, base_url)

    delete_found = False
    for patt in (r"Delete\s*All|Xoá\s*Tất\s*Cả|清空|删除全部"):
        with contextlib.suppress(Exception):
            if new_page.get_by_role("button", name=re.compile(patt, re.I)).first.is_visible():
                delete_found = True
                break
    assert not delete_found, "Super Admin should not see 'Delete All' control (platform-admin only)"
