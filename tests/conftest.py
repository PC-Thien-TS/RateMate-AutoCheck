# -*- coding: utf-8 -*-
import os

# Ensure core fixtures are loaded across the test suite
pytest_plugins = [
    "tests._fixtures.config",
    "tests._fixtures.playwright",
    "tests._fixtures.roles",
]


def _site_key_aliases() -> set[str]:
    raw = (os.getenv("SITE") or "ratemate").strip().upper()
    aliases = {raw}
    if raw in {"RATEMATE1", "RATEMATE2"}:
        aliases.add("RATEMATE")
    return aliases


def _pick_cred(name: str) -> str:
    aliases = _site_key_aliases()
    # Site-scoped then global
    order = []
    for key in aliases:
        order.append(f"E2E_{key}_{name}")
        order.append(f"{key}_E2E_{name}")
    order.append(f"E2E_{name}")
    for envn in order:
        val = os.getenv(envn)
        if val:
            return val
    return ""


def _has_creds() -> bool:
    return bool(_pick_cred("EMAIL") and _pick_cred("PASSWORD"))


def pytest_collection_modifyitems(config, items):
    """Remove login-required tests from collection when no credentials provided.

    This avoids runtime skip noise and shortens reports.
    """
    if _has_creds():
        return

    drop_substrings = [
        # Auth suite
        "tests/auth/test_login.py::test_login_success",
        # Smoke protected-after-login checks
        "tests/smoke/test_routes.py::test_protected_routes_after_login",
    ]

    keep = []
    for item in items:
        nid = getattr(item, "nodeid", "")
        if any(sub in nid for sub in drop_substrings):
            continue
        keep.append(item)

    if len(keep) != len(items):
        items[:] = keep
