#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Load discover targets from YAML and run auto-discover + generated tests.

Usage:
  python tools/discover_from_targets.py \
    --file config/discover/targets.yml \
    --emit-tests --emit-yaml --run-tests

Notes:
- Do not put secrets in the YAML. Use environment variables (E2E_*).
- Per-target env precedence for creds is handled by conftest/site fixtures.
"""

from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


def sh(args: list[str], cwd: str | None = None, env: dict[str, str] | None = None) -> int:
    print("$", " ".join(args))
    return subprocess.call(args, cwd=cwd, env=env or os.environ.copy())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="config/discover/targets.yml")
    ap.add_argument("--emit-tests", action="store_true", default=True)
    ap.add_argument("--emit-yaml", action="store_true", default=True)
    ap.add_argument("--run-tests", action="store_true", default=True)
    ap.add_argument("--workdir", default=".")
    args = ap.parse_args(argv)

    p = Path(args.file)
    if not p.is_file():
        print(f"[targets] File not found: {p}", file=sys.stderr)
        return 2

    data: Dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    defaults: Dict[str, Any] = data.get("defaults", {}) if isinstance(data.get("defaults"), dict) else {}
    targets = data.get("targets") or []
    if not isinstance(targets, list) or not targets:
        print("[targets] No targets defined", file=sys.stderr)
        return 2

    workdir = Path(args.workdir)
    out_report = workdir / "report" / "discover"
    out_report.mkdir(parents=True, exist_ok=True)

    for t in targets:
        if not isinstance(t, dict):
            continue
        site = str(t.get("site") or "").strip()
        seeds = t.get("seeds") or []
        base_url = (t.get("base_url") or "").strip()
        login_path = (t.get("login_path") or "").strip()
        if not site or not seeds:
            print(f"[targets] skip invalid target: {t}")
            continue

        # Build args for discover
        allow = t.get("allow") or defaults.get("allow") or []
        deny = t.get("deny") or defaults.get("deny") or []
        navs = t.get("nav_selectors") or defaults.get("nav_selectors") or []
        login_first = bool(t.get("login_first", defaults.get("login_first", True)))

        for url in seeds:
            cmd = [sys.executable, "tools/discover_routes.py", "--url", url, "--emit-tests", "--emit-yaml",
                   "--screenshot-dir", str(out_report)]
            if login_first:
                cmd.append("--login-first")
            for a in allow:
                cmd += ["--allow", a]
            for d in deny:
                cmd += ["--deny", d]
            for sel in navs:
                cmd += ["--nav-selectors", sel]
            env = os.environ.copy()
            if base_url:
                env["BASE_URL"] = base_url
            if login_path:
                env["LOGIN_PATH"] = login_path
            env["SITE"] = site
            rc = sh(cmd, cwd=str(workdir), env=env)
            if rc != 0:
                print(f"[discover] WARN: discover exited {rc} for {url}")

        # Run generated tests for this site
        if args.run_tests:
            gen_file = workdir / "tests" / "generated" / f"test_{site}_routes_generated.py"
            if gen_file.is_file():
                browsers = t.get("browsers") or defaults.get("browsers") or ["chromium"]
                markers = str(t.get("markers") or defaults.get("markers") or "smoke").strip()
                for br in browsers:
                    cmd = [sys.executable, "-m", "pytest", "-vv", str(gen_file), "--browser", br,
                           "--screenshot=only-on-failure", "--video=off", "--tracing=retain-on-failure"]
                    if markers:
                        cmd += ["-m", markers]
                    env = os.environ.copy()
                    env["SITE"] = site
                    if base_url:
                        env["BASE_URL"] = base_url
                    if login_path:
                        env["LOGIN_PATH"] = login_path
                    sh(cmd, cwd=str(workdir), env=env)
            else:
                print(f"[targets] No generated file for site={site}: {gen_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

