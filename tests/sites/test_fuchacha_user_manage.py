# -*- coding: utf-8 -*-
import re
import contextlib
import pytest

from pages.auth.login_page import LoginPage


@pytest.mark.smoke
@pytest.mark.auth
def test_user_manage_basic(new_page, site, base_url, auth_paths, credentials):
    """Fuchacha: login and open User Manage, verify basic UI parts.

    Skips unless SITE=fuchacha and credentials are present.
    """
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")

    if not (credentials.get("email") and credentials.get("password")):
        pytest.skip("Missing E2E_EMAIL/E2E_PASSWORD")

    # Login
    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto()
    lp.login(credentials["email"], credentials["password"])  # best-effort

    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(400)

    # Navigate to User Manage
    um_path = "/system-manage/user-manage"
    new_page.goto(f"{base_url.rstrip('/')}{um_path}", wait_until="domcontentloaded")
    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(500)

    # Assertions: presence of key controls/text
    # Headings / tabs
    ok_any = False
    with contextlib.suppress(Exception):
        ok_any = new_page.get_by_role("heading", name=re.compile(r"user\s*manage", re.I)).first.is_visible()

    if not ok_any:
        with contextlib.suppress(Exception):
            ok_any = new_page.get_by_text(re.compile(r"User\s*Manage|User\s*List", re.I)).first.is_visible()

    assert ok_any, "Expected User Manage view to be visible"

    # Search input exists
    found_search = False
    with contextlib.suppress(Exception):
        found_search = new_page.get_by_placeholder(re.compile(r"search|user\s*name", re.I)).first.is_visible()
    if not found_search:
        with contextlib.suppress(Exception):
            found_search = new_page.get_by_role("textbox", name=re.compile(r"search|user\s*name", re.I)).first.is_visible()
    assert found_search, "Search box not found"

    # Action buttons present (Add / Edit / Delete — any of them)
    btn_ok = False
    for patt in (r"Add|Create|New|Thêm|新增", r"Edit|Sửa|编辑", r"Delete|Xoá|删除"):
        with contextlib.suppress(Exception):
            if new_page.get_by_role("button", name=re.compile(patt, re.I)).first.is_visible():
                btn_ok = True
                break
    assert btn_ok, "Expected at least one action button (Add/Edit/Delete)"

