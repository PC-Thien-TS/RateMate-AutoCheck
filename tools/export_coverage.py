#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Export a concise coverage summary of what links/routes and feature areas were tested.

Usage:
  python tools/export_coverage.py --site ratemate_app2 --junit report/junit.xml --out report

If --junit is omitted, the script tries to find a JUnit file in report/*.xml.
Outputs:
  - report/coverage.json
  - report/coverage.md
  - report/links_tested.csv
"""

from __future__ import annotations
import argparse
import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass
class Case:
    name: str
    classname: str
    status: str  # pass | fail | error | skip
    time: float


def _find_junit(path_hint: str | None) -> str | None:
    if path_hint and Path(path_hint).is_file():
        return path_hint
    cands = sorted(glob.glob("report/*.xml"))
    for p in cands[::-1]:
        try:
            root = ET.parse(p).getroot()
            if root.tag.endswith("testsuite") or root.find(".//testsuite") is not None:
                return p
        except Exception:
            continue
    return None


def _parse_junit(path: str) -> list[Case]:
    cases: list[Case] = []
    root = ET.parse(path).getroot()
    suites = [root] if root.tag.endswith("testsuite") else list(root.findall(".//testsuite"))
    for ts in suites:
        for tc in ts.findall(".//testcase"):
            name = (tc.get("name") or "").strip()
            classname = (tc.get("classname") or "").strip()
            try:
                t = float(tc.get("time", "0") or 0.0)
            except Exception:
                t = 0.0
            status = "pass"
            if tc.find("failure") is not None:
                status = "fail"
            elif tc.find("error") is not None:
                status = "error"
            elif tc.find("skipped") is not None:
                status = "skip"
            cases.append(Case(name=name, classname=classname, status=status, time=t))
    return cases


def _browser_and_param(name: str) -> tuple[str | None, str | None]:
    # test_fn[chromium-/en/login] or test_fn[chromium-public:/login]
    if "[" not in name:
        return None, None
    br = name.split("[", 1)[1].rstrip("]")
    if not br:
        return None, None
    if "-" in br:
        b, param = br.split("-", 1)
        return b, param
    return br, None


def _collect_links_and_routes(cases: list[Case]):
    links: list[dict] = []
    routes: list[dict] = []
    for c in cases:
        mod = c.classname  # e.g., tests.smoke.test_links
        if mod.endswith("test_links") and c.name.startswith("test_open_links_ok"):
            br, param = _browser_and_param(c.name)
            path = param or ""
            links.append({
                "browser": br,
                "path": path,
                "status": c.status,
                "time": c.time,
            })
        elif mod.endswith("test_routes") and c.name.startswith("test_routes_access"):
            br, param = _browser_and_param(c.name)
            kind, path = None, None
            if param and ":" in param:
                kind, path = param.split(":", 1)
            routes.append({
                "browser": br,
                "kind": kind,
                "path": path,
                "status": c.status,
                "time": c.time,
            })
    return links, routes


def _feature_buckets(cases: list[Case]) -> dict[str, list[str]]:
    buckets: dict[str, set[str]] = {}
    def add(key: str, label: str):
        buckets.setdefault(key, set()).add(label)

    for c in cases:
        mod = c.classname
        base = c.name.split("[", 1)[0]
        if mod.endswith("tests.auth.test_login"):
            add("auth", base)
        elif mod.endswith("tests.auth.test_register"):
            add("auth", base)
        elif mod.endswith("tests.i18n.test_language_switch"):
            add("i18n", base)
        elif ".tests.sites." in mod:
            add("sites", base)
        elif mod.endswith("tests.smoke.test_links"):
            add("smoke", base)
        elif mod.endswith("tests.smoke.test_routes"):
            add("smoke", base)
        else:
            add("other", f"{mod}:{base}")
    return {k: sorted(v) for k, v in buckets.items()}


def _load_discovered(site: str | None) -> dict:
    if not site:
        return {}
    p = Path(f"config/discovered/{site}.json")
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _md_table(rows: list[list[str]]) -> str:
    if not rows:
        return "(none)"
    widths = [max(len(str(cell)) for cell in col) for col in zip(*rows)]
    def fmt(r):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |"
    hdr = fmt(rows[0])
    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    body = [fmt(r) for r in rows[1:]]
    return "\n".join([hdr, sep, *body])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", help="Site key (used to read discovered JSON)")
    ap.add_argument("--junit", help="Path to JUnit XML (default: search report/*.xml)")
    ap.add_argument("--out", default="report", help="Output directory (default: report)")
    args = ap.parse_args(argv)

    junit_path = _find_junit(args.junit)
    if not junit_path:
        print("[coverage] WARN: JUnit XML not found; nothing to export")
        return 0

    cases = _parse_junit(junit_path)
    links, routes = _collect_links_and_routes(cases)
    features = _feature_buckets(cases)
    discovered = _load_discovered(args.site)

    out = {
        "site": args.site or os.getenv("SITE") or "",
        "junit": junit_path,
        "links": links,
        "routes": routes,
        "features": features,
        "discovered": discovered,
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "coverage.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Write CSV for links
    csv_lines = ["browser,path,status,time"]
    for it in links:
        csv_lines.append(
            f"{it.get('browser') or ''},{it.get('path') or ''},{it.get('status')},{it.get('time')}"
        )
    (out_dir / "links_tested.csv").write_text("\n".join(csv_lines), encoding="utf-8")

    # Markdown summary
    md: list[str] = []
    md.append(f"# Coverage Summary (site={out['site']})\n")
    md.append(f"JUnit: `{junit_path}`\n")
    md.append("## Links Tested\n")
    rows = [["Browser", "Path", "Status", "Time"]]
    for it in links:
        rows.append([it.get("browser") or "", it.get("path") or "", it.get("status") or "", f"{it.get('time', 0):.2f}s"])
    md.append(_md_table(rows) + "\n")
    md.append("## Routes Tested\n")
    rows = [["Browser", "Kind", "Path", "Status", "Time"]]
    for it in routes:
        rows.append([it.get("browser") or "", it.get("kind") or "", it.get("path") or "", it.get("status") or "", f"{it.get('time', 0):.2f}s"])
    md.append(_md_table(rows) + "\n")
    md.append("## Feature Areas\n")
    for k in ("auth", "smoke", "i18n", "sites", "other"):
        lst = features.get(k) or []
        if not lst:
            continue
        md.append(f"- {k}: " + ", ".join(lst))
    md.append("")
    if discovered:
        md.append("## Discovered (from config/discovered)\n")
        md.append("- base_url: " + str(discovered.get("base_url", "")))
        md.append("- login_path: " + str(discovered.get("login_path", "")))
        pubs = discovered.get("public") or []
        prots = discovered.get("protected") or []
        md.append(f"- public ({len(pubs)}): " + ", ".join(pubs))
        md.append(f"- protected ({len(prots)}): " + ", ".join(prots))

    (out_dir / "coverage.md").write_text("\n".join(md), encoding="utf-8")
    print(f"[coverage] Wrote {out_dir/'coverage.json'} and {out_dir/'coverage.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

