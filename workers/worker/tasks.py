import json
import os
import time
from pathlib import Path
from typing import Dict


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
    url = payload.get("url")
    test_type = payload.get("test_type")

    # Simulate different durations by test type
    delay = {"smoke": 2, "full": 4, "performance": 3, "security": 3}.get(test_type, 2)
    time.sleep(delay)

    # Placeholder result; integrate Playwright/Lighthouse/etc. here
    result = {
        "url": url,
        "test_type": test_type,
        "passed": True,
        "metrics": {"lcp": 2.1, "cls": 0.01, "fid": 10} if test_type == "performance" else None,
        "alerts": [] if test_type != "security" else [
            {"severity": "Low", "title": "X-Frame-Options missing on /"}
        ],
    }
    out_path = RESULTS_DIR / f"{job_id}-result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _update(job_id, {"status": "completed", "result_path": str(out_path)})


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

