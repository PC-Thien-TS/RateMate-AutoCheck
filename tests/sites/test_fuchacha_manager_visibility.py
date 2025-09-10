# -*- coding: utf-8 -*-
import os
import re
import contextlib
import pytest

from pages.auth.login_page import LoginPage


@pytest.mark.smoke
def test_manager_sees_counts_not_phone_numbers(new_page, site, base_url, auth_paths, manager_credentials):
    """Manager should not see raw phone numbers on summary screens.

    Heuristic: ensure page does not show long digit sequences (>=9) when listing users.
    Skips if SITE!=fuchacha or manager credentials missing.
    """
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")
    if not (manager_credentials.get("email") and manager_credentials.get("password")):
        pytest.skip("Missing manager credentials")

    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto(); lp.login(manager_credentials["email"], manager_credentials["password"]) 
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)

    # Navigate to User Manage
    new_page.goto(f"{base_url.rstrip('/')}/system-manage/user-manage", wait_until="domcontentloaded")
    with contextlib.suppress(Exception):
        new_page.wait_for_timeout(400)

    # Collect visible text
    body_text = ""
    with contextlib.suppress(Exception):
        body_text = new_page.locator("body").inner_text(timeout=1000)
    # Look for sequences of 9+ digits (typical for phone numbers); should be absent
    has_raw_numbers = bool(re.search(r"(?<!\d)\d{9,}(?!\d)", body_text or ""))
    assert not has_raw_numbers, "Manager view should not expose raw phone numbers"

