# -*- coding: utf-8 -*-
import contextlib
import pytest


@pytest.fixture
def new_page(context):
    page = context.new_page()
    page.set_default_timeout(30_000)
    page.set_default_navigation_timeout(45_000)
    try:
        yield page
    finally:
        with contextlib.suppress(Exception):
            page.close()


@pytest.fixture(scope="session", autouse=True)
def _patch_login_fill_force():
    try:
        from pages import common_helpers as _ch  # type: ignore
    except Exception:
        return

    def _fill_force(locator, value, timeout: int = 10_000):
        locator.wait_for(state="visible", timeout=timeout)
        try:
            locator.click()
            locator.fill("")
            locator.fill(str(value), timeout=timeout)
        except Exception:
            locator.evaluate(
                """(el, v) => {
                    el.focus();
                    el.value = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.value = String(v);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                str(value),
            )

    try:
        _ch.fill_force = _fill_force  # type: ignore[attr-defined]
    except Exception:
        pass

