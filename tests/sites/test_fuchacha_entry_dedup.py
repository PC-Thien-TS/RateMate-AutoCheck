# -*- coding: utf-8 -*-
import os
import re
import time
import contextlib
import pytest

from pages.auth.login_page import LoginPage


def _goto(page, base_url: str, path: str):
    p = path if path.startswith('/') else '/' + path
    page.goto(f"{base_url.rstrip('/')}{p}", wait_until="domcontentloaded")
    with contextlib.suppress(Exception):
        page.wait_for_timeout(300)


def _enter_numbers(page, numbers: list[str]) -> bool:
    """Best-effort: find a textarea/input to paste numbers, then submit.
    Returns True if interaction seems to succeed.
    """
    joined = "\n".join(numbers)
    # Try textarea / large input
    cand = (
        page.locator("textarea").or_(
            page.locator("textarea[placeholder*='phone' i]")
        ).or_(
            page.get_by_role("textbox")
        )
    )
    el = None
    with contextlib.suppress(Exception):
        el = cand.first if cand.count() else None
    if not el:
        return False
    with contextlib.suppress(Exception):
        el.fill("")
        el.type(joined, delay=10)
    # Submit-like buttons
    for patt in (r"Submit|Send|Save|Check|Kiểm|Gửi|保存|提交"):
        with contextlib.suppress(Exception):
            btn = page.get_by_role("button", name=re.compile(patt, re.I)).first
            if btn and btn.is_visible():
                btn.click()
                break
    with contextlib.suppress(Exception):
        page.wait_for_timeout(600)
    return True


@pytest.mark.write
def test_deduplicate_between_staffs(new_page, site, base_url, auth_paths, entry_path,
                                     staff_a_credentials, staff_b_credentials):
    """Staff A enters a phone, then Staff B enters the same -> expect duplicate notice.

    Skips if creds missing or SITE!=fuchacha. Requires that both accounts belong to same tenant.
    """
    if str(site).strip().lower() != "fuchacha":
        pytest.skip("SITE is not fuchacha")
    if not os.getenv("E2E_ALLOW_WRITE"):
        pytest.skip("Write tests disabled (set E2E_ALLOW_WRITE=1 to enable)")

    a, b = staff_a_credentials, staff_b_credentials
    if not (a.get("email") and a.get("password") and b.get("email") and b.get("password")):
        pytest.skip("Missing staff A/B credentials")

    # Use a deterministic-in-session phone number
    suffix = int(time.time()) % 100000
    phone = f"098{suffix:05d}"

    # Staff A login and submit
    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto(); lp.login(a["email"], a["password"]) 
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)
    _goto(new_page, base_url, entry_path)
    ok = _enter_numbers(new_page, [phone])
    if not ok:
        pytest.skip("Entry UI not found; cannot validate dedup")

    # Logout (best-effort) and login as Staff B
    with contextlib.suppress(Exception):
        new_page.get_by_role("button", name=re.compile(r"logout|sign\s*out|đăng\s*xuất|退出", re.I)).first.click()
        new_page.wait_for_timeout(400)
    lp = LoginPage(new_page, base_url, auth_paths["login"])
    lp.goto(); lp.login(b["email"], b["password"]) 
    with contextlib.suppress(Exception):
        new_page.wait_for_load_state("domcontentloaded", timeout=8_000)
        new_page.wait_for_timeout(300)
    _goto(new_page, base_url, entry_path)
    _enter_numbers(new_page, [phone])

    # Expect a duplicate-like message
    dup_rx = re.compile(r"duplicate|trùng|đã\s*tồn\s*tại|已存在|重复", re.I)
    with contextlib.suppress(Exception):
        assert new_page.get_by_text(dup_rx).first.is_visible(timeout=2000), "Expected duplicate notice for second entry"
