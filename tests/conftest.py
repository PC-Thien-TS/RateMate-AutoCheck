# -*- coding: utf-8 -*-
# Aggregated fixtures for pytest: load modular fixtures.
from _fixtures.config import *  # noqa
from _fixtures.playwright import *  # noqa
from _fixtures.roles import *  # noqa


def pytest_collection_modifyitems(items):
    """Attach test case metadata (from @pytest.mark.tc) into JUnit properties.

    Usage in tests:
        @pytest.mark.tc(id="RM-LOGIN-001", title="Login success", area="Auth", severity="High")
        def test_login_success(...): ...
    """
    for item in items:
        try:
            mark = item.get_closest_marker("tc")
        except Exception:
            mark = None
        if not mark:
            continue
        props = getattr(item, "user_properties", None)
        if props is None:
            try:
                item.user_properties = []  # type: ignore[attr-defined]
            except Exception:
                continue
            props = item.user_properties  # type: ignore[attr-defined]
        try:
            for k, v in (mark.kwargs or {}).items():
                props.append((str(k), str(v)))  # type: ignore[attr-defined]
        except Exception:
            pass


# ---------------- Enhanced reporting (HTML/JUnit metadata) ----------------
import os
import re
from typing import Tuple

try:
    # pytest-html uses py.xml.html for table cell helpers
    from py.xml import html  # type: ignore
except Exception:  # pragma: no cover - fallback if plugin not present
    html = None  # type: ignore


def _tc_info(item) -> Tuple[str, str]:
    try:
        m = item.get_closest_marker("tc")
        if m and getattr(m, "kwargs", None):
            cid = str(m.kwargs.get("id", "") or "")
            title = str(m.kwargs.get("title", "") or "")
            return cid, title
    except Exception:
        pass
    return "", ""


def _browser_from_nodeid(nodeid: str) -> str:
    try:
        m = re.search(r"\[([^\]]+)\]", nodeid or "")
        token = (m.group(1) if m else "").split("-", 1)[0].strip().lower()
        return token if token in ("chromium", "firefox", "webkit") else ""
    except Exception:
        return ""


def pytest_configure(config):
    # Populate HTML metadata header if pytest-html + pytest-metadata present
    try:
        meta = getattr(config, "_metadata", None)
        if isinstance(meta, dict):
            site = os.getenv("SITE", "").strip()
            base = os.getenv("BASE_URL", "") or os.getenv("BASE_URL_PROD", "")
            meta.setdefault("Site", site or "(unset)")
            meta.setdefault("Base URL", base or "(unset)")
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    # Compact end-of-run summary emphasizing pass/fail/error counts
    try:
        rep = session.testsfailed  # triggers creation of stats
        # Access internal stats dict
        stats = getattr(session, "stats", {}) or {}
        total = sum(len(v) for k, v in stats.items() if k in {"passed", "failed", "error", "skipped"})
        failed = len(stats.get("failed", []))
        errored = len(stats.get("error", []))
        skipped = len(stats.get("skipped", []))
        passed = max(total - failed - errored - skipped, 0)
        print(f"\n== Result: {total} tests | pass={passed} fail={failed} error={errored} skip={skipped}")
    except Exception:
        pass


def pytest_html_report_title(report):  # type: ignore[func-returns-value]
    # Customize HTML report title to include SITE if set
    site = os.getenv("SITE", "").strip()
    return f"Test Report - {site}" if site else "Test Report"


import pytest as _pytest  # local alias to avoid confusion


@_pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    try:
        cid, title = _tc_info(item)
        rep.case_id = cid  # for pytest-html table row
        rep.case_title = title
        rep.browser = _browser_from_nodeid(item.nodeid)
        # Also expose as user_properties so they appear in JUnit properties
        props = getattr(rep, "user_properties", None) or []
        if cid:
            props.append(("case_id", cid))
        if title:
            props.append(("case_title", title))
        if rep.browser:
            props.append(("browser", rep.browser))
        rep.user_properties = props
    except Exception:
        pass


def pytest_html_results_table_header(cells):  # type: ignore[func-returns-value]
    if not html:
        return
    # Insert columns after the first default column (Test)
    cells.insert(1, html.th("Case ID"))
    cells.insert(2, html.th("Title"))
    cells.insert(3, html.th("Browser"))


def pytest_html_results_table_row(report, cells):  # type: ignore[func-returns-value]
    if not html:
        return
    cid = getattr(report, "case_id", "")
    title = getattr(report, "case_title", "")
    browser = getattr(report, "browser", "")
    cells.insert(1, html.td(cid))
    cells.insert(2, html.td(title))
    cells.insert(3, html.td(browser))
