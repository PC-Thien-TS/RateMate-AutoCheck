import os
import pathlib


def pytest_ignore_collect(path, config):
    p = pathlib.Path(str(path))
    # Only collect fuchacha site tests when SITE=fuchacha
    if p.name.startswith("test_fuchacha_"):
        site = (os.getenv("SITE") or "").strip().lower()
        if site != "fuchacha":
            return True
    return False

