# -*- coding: utf-8 -*-
import os
import pytest


def _role_credentials(role: str | None, global_fallback: dict) -> dict:
    site_key = (os.getenv("SITE") or "ratemate").strip().upper()

    def pick(name: str) -> str:
        names = []
        if role:
            r = role.strip().upper()
            names += [f"E2E_{site_key}_{r}_{name}", f"E2E_{r}_{name}"]
        names += [f"E2E_{site_key}_{name}", f"{site_key}_E2E_{name}", f"E2E_{name}"]
        for envn in names:
            val = os.getenv(envn)
            if val:
                return val
        return (global_fallback.get("email") if name == "EMAIL" else global_fallback.get("password")) or ""

    return {"email": pick("EMAIL"), "password": pick("PASSWORD")}


@pytest.fixture(scope="session")
def platform_admin_credentials(credentials) -> dict:
    return _role_credentials("PLATFORM_ADMIN", credentials)


@pytest.fixture(scope="session")
def super_admin_credentials(credentials) -> dict:
    return _role_credentials("SUPER_ADMIN", credentials)


@pytest.fixture(scope="session")
def manager_credentials(credentials) -> dict:
    return _role_credentials("MANAGER", credentials)


@pytest.fixture(scope="session")
def staff_a_credentials(credentials) -> dict:
    return _role_credentials("STAFF_A", credentials)


@pytest.fixture(scope="session")
def staff_b_credentials(credentials) -> dict:
    return _role_credentials("STAFF_B", credentials)


@pytest.fixture(scope="session")
def entry_path() -> str:
    return (os.getenv("E2E_ENTRY_PATH") or "/customer-channels").strip()

