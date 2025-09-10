# -*- coding: utf-8 -*-
import os
import re
import contextlib
import pytest

from pages.auth.login_page import LoginPage


def _goto(new_page, base_url: str, path: str):
    p = path if path.startswith('/') else '/' + path
    new_page.goto(f"{base_url.rstrip('/')}{p}", wait_until="domcontentloaded")
    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(300)


def _visible_text(new_page, rx: str) -> bool:
    with contextlib.suppress(Exception):
        return new_page.get_by_text(re.compile(rx, re.I)).first.is_visible()
    return False


@pytest.mark.smoke
def test_staff_cannot_access_user_manage(new_page, site, base_url, auth_paths):
    """Staff should not access /system-manage/user-manage.

    Uses env E2E_T1_STAFF_A_EMAIL / E2E_T1_STAFF_A_PASSWORD.
    Skips if SITE != fuchacha or creds missing.
    """
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")

    email = os.getenv("E2E_T1_STAFF_A_EMAIL") or os.getenv("E2E_EMAIL")
    password = os.getenv("E2E_T1_STAFF_A_PASSWORD") or os.getenv("E2E_PASSWORD")
    if not (email and password):
        pytest.skip("Missing staff credentials (E2E_T1_STAFF_A_* or E2E_*)")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto()
    lp.login(email, password)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)

    target = "/system-manage/user-manage"
    _goto(new_page, base_url, target)

    # Expect one of:
    # - redirected back to login
    # - 403/Unauthorized message
    # - blank table without admin controls
    redirected_to_login = bool(re.search(r"/log[-_]?in|/sign[-_]?in", new_page.url, re.I))
    unauthorized_msg = _visible_text(new_page, r"unauthorized|forbidden|không\s*có\s*quyền|权限不足|没有权限")

    # Admin-only controls text to check absence
    admin_controls_text = (
        _visible_text(new_page, r"User\s*Manage|用户管理|Quản\s*trị\s*người\s*dùng")
        and _visible_text(new_page, r"Add|Create|New|Thêm|新增")
    )

    assert redirected_to_login or unauthorized_msg or (not admin_controls_text), (
        f"Staff should not access {target}, but admin controls appear"
    )

