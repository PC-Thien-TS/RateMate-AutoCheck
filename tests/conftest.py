# -*- coding: utf-8 -*-
# Aggregated fixtures for pytest: load modular fixtures.
from _fixtures.config import *  # noqa
from _fixtures.playwright import *  # noqa
from _fixtures.roles import *  # noqa

# --- Start of Custom Excel Report Generation ---
import os
import re
import pathlib
from typing import Tuple
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

# Global list to store test results for the Excel report
excel_report_data = []

def _parse_docstring(doc: str) -> dict:
    """Parses a structured docstring to extract report fields."""
    if not doc:
        return {}
    
    doc = doc.strip()
    lines = doc.splitlines()
    
    data = {}
    current_key = None
    current_content = []

    key_map = {
        "precondition:": "precondition",
        "test steps:": "test_steps",
        "expected result:": "expected_result",
    }

    for line in lines:
        line_lower = line.strip().lower()
        if line_lower in key_map:
            if current_key:
                data[current_key] = "\n".join(current_content).strip()
            
            current_key = key_map[line_lower]
            current_content = []
        elif current_key:
            current_content.append(line.strip())

    if current_key:
        data[current_key] = "\n".join(current_content).strip()
        
    return data
# --- End of Custom Excel Report Generation ---


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
        m = re.search(r"\\[([^\\]+)\\]", nodeid or "")
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
    # --- Original sessionfinish logic ---
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
    
    # --- New: Generate Custom Excel report ---
    print("\n[report] Generating custom Excel report...")
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Report"

    headers = [
        "Test Case ID", "Title", "Status", "Duration", 
        "Precondition", "Test Steps", "Expected Result"
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")

    for result in excel_report_data:
        row = [
            result["id"], result["title"], result["status"], result["duration"],
            result["precondition"], result["test_steps"], result["expected_result"],
        ]
        ws.append(row)

    for i, col in enumerate(ws.columns):
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_len:
                    max_len = len(cell.value)
            except:
                pass
        adjusted_width = (max_len + 2)
        ws.column_dimensions[col_letter].width = min(adjusted_width, 60) # Cap width at 60

    report_dir = pathlib.Path("report")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / "run.xlsx"
    try:
        wb.save(report_path)
        print(f"[report] Custom Excel report saved to {report_path}")
    except Exception as e:
        print(f"[report] ERROR: Failed to save Excel report: {e}")


def pytest_html_report_title(report):  # type: ignore[func-returns-value]
    # Customize HTML report title to include SITE if set
    site = os.getenv("SITE", "").strip()
    return f"Test Report - {site}" if site else "Test Report"


import pytest as _pytest  # local alias to avoid confusion


@_pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    rep.item = item

    # --- New: Capture data for Excel report ---
    if rep.when == "call":
        cid, title = _tc_info(item)
        docstring_data = _parse_docstring(item.obj.__doc__ if hasattr(item, 'obj') and item.obj.__doc__ else '')
        
        status = "Passed"
        if rep.failed:
            status = "Failed"
        elif rep.skipped:
            status = "Skipped"

        excel_report_data.append({
            "id": cid, "title": title, "status": status, "duration": f"{rep.duration:.2f}s",
            "precondition": docstring_data.get("precondition", ""),
            "test_steps": docstring_data.get("test_steps", ""),
            "expected_result": docstring_data.get("expected_result", ""),
        })

    # --- Original makereport logic for HTML/JUnit ---
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