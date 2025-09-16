import os
import pathlib


def pytest_ignore_collect(path, config):
    try:
        p = pathlib.Path(str(path))
        if p.name == "test_ratemate_app2_routes_generated.py":
            site = (os.getenv("SITE") or "ratemate").strip().lower()
            if site != "ratemate_app2":
                return True
    except Exception:
        pass
    return False

