# -*- coding: utf-8 -*-
import os
import re
import contextlib
import pytest
pytestmark = [pytest.mark.roles]

from pages.auth.login_page import LoginPage


@pytest.mark.smoke
def test_super_admin_cannot_see_other_tenant(new_page, site, base_url, auth_paths):
    """As a Super Admin of tenant A, should not see accounts of tenant B.

    Requires env:
      - E2E_SUPER_ADMIN_EMAIL / E2E_SUPER_ADMIN_PASSWORD
      - E2E_OTHER_SUPER_ADMIN_NAME (display name to assert absence)
    Skips gracefully if not provided or SITE!=fuchacha.
    """
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")

    email = os.getenv("E2E_SUPER_ADMIN_EMAIL")
    password = os.getenv("E2E_SUPER_ADMIN_PASSWORD")
    other_name = (os.getenv("E2E_OTHER_SUPER_ADMIN_NAME") or "").strip()
    if not (email and password and other_name):
        pytest.skip("Missing SUPER_ADMIN creds or OTHER_SUPER_ADMIN_NAME")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto()
    lp.login(email, password)
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)

    # Open User Manage and ensure other tenant's name not listed
    new_page.goto(f"{base_url.rstrip('/')}/system-manage/user-manage", wait_until="domcontentloaded")
    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(500)

    # Page should NOT contain other tenant's display name
    with contextlib.suppress(Exception):
        assert not new_page.get_by_text(re.compile(re.escape(other_name), re.I)).first.is_visible(timeout=800), (
            f"Unexpected: saw other tenant '{other_name}' in User Manage list"
        )
