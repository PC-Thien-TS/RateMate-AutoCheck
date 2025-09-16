import os
import pathlib
from typing import List, Tuple

import yaml


def _read_locales_from_config(site: str) -> List[str]:
    site = (site or "ratemate").strip()
    # Prefer per-site config
    for ext in ("yml", "yaml"):
        p = pathlib.Path(f"config/sites/{site}.{ext}")
        if p.is_file():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                loc = data.get("locales")
                if isinstance(loc, list):
                    return [str(x).strip().lower() for x in loc if str(x).strip()]
            except Exception:
                pass
            break
    # Fallback to aggregated sites.yaml
    for name in ("config/sites.yaml", "config/sites.yml"):
        p = pathlib.Path(name)
        if p.is_file():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                sites = data.get("sites") or {}
                cfg = sites.get(site, {}) if isinstance(sites, dict) else {}
                loc = cfg.get("locales")
                if isinstance(loc, list):
                    return [str(x).strip().lower() for x in loc if str(x).strip()]
            except Exception:
                pass
            break
    return []


def pytest_ignore_collect(path, config):
    p = pathlib.Path(str(path))
    if p.name != "test_language_switch.py":
        return False

    # Determine locales from env or config
    raw = (os.getenv("LOCALES") or os.getenv("SITE_LOCALES") or "").strip()
    if raw:
        locales = [c.strip().lower() for c in raw.split(",") if c.strip()]
    else:
        site = (os.getenv("SITE") or "ratemate").strip()
        locales = _read_locales_from_config(site)

    # If VI not configured, ignore collecting this module entirely
    return "vi" not in set(locales)

