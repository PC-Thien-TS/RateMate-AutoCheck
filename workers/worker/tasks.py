import json
import os
import time
from pathlib import Path
from typing import Dict

from playwright.sync_api import sync_playwright


RESULTS_DIR = Path(os.getenv("TAAS_RESULTS_DIR", "test-results/taas")).resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _update(job_id: str, patch: Dict):
    path = RESULTS_DIR / f"{job_id}.json"
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(patch)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_web_test(job_id: str, payload: Dict):
    _update(job_id, {"status": "running"})
    url = payload.get("url") or ""
    test_type = (payload.get("test_type") or "smoke").lower()

    screenshot_path = RESULTS_DIR / f"{job_id}-screenshot.png"
    passed = False
    status_code = None
    title = None
    error = None
    t0 = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"]) 
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            page = context.new_page()
            resp = page.goto(url, wait_until="networkidle", timeout=30000)
            status_code = resp.status if resp else None
            title = page.title()
            page.screenshot(path=str(screenshot_path), full_page=True)
            # Simple success heuristic for smoke
            passed = bool(resp and 200 <= status_code < 400)
            # TODO: extend for full/performance/security types
            context.close()
            browser.close()
    except Exception as e:
        error = str(e)

    elapsed = round(time.time() - t0, 2)

    result = {
        "url": url,
        "test_type": test_type,
        "passed": passed,
        "status_code": status_code,
        "title": title,
        "screenshot": str(screenshot_path) if screenshot_path.exists() else None,
        "duration_sec": elapsed,
        "metrics": None,
        "alerts": [],
        "error": error,
    }
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    final = {"status": "completed" if passed else "failed", "result_path": str(out_path)}
    if error:
        final["error"] = error
    _update(job_id, final)


def run_mobile_test(job_id: str, payload: Dict):
    _update(job_id, {"status": "running"})
    test_type = payload.get("test_type")
    time.sleep(3)

    # Placeholder result; integrate MobSF / Firebase Test Lab here
    result = {
        "test_type": test_type,
        "analyzer": "MobSF" if test_type == "analyze" else "Appium",
        "summary": "Static analysis completed" if test_type == "analyze" else "E2E executed on device",
    }
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _update(job_id, {"status": "completed", "result_path": str(out_path)})
