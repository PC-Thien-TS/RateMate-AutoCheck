import os
import uuid
import json
from pathlib import Path
from typing import Optional, Literal

from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AnyUrl
from rq import Queue
from redis import Redis


# ---------- Config ----------
RESULTS_DIR = Path(os.getenv("TAAS_RESULTS_DIR", "test-results/taas")).resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("TAAS_QUEUE_NAME", "taas")
API_KEY = os.getenv("API_KEY", "dev-key")


def _redis_conn() -> Redis:
    return Redis.from_url(REDIS_URL)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_redis_conn())


def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    if not API_KEY:
        return True  # disabled
    if x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return True


# ---------- Models ----------
class WebTestRequest(BaseModel):
    url: AnyUrl
    test_type: Literal["smoke", "full", "performance", "security"] = "smoke"
    site: Optional[str] = None


class MobileDevice(BaseModel):
    name: Optional[str] = None
    platform: Literal["android", "ios"] = "android"
    os_version: Optional[str] = None
    is_emulator: Optional[bool] = True


class MobileTestRequest(BaseModel):
    apk_url: Optional[str] = None
    ipa_url: Optional[str] = None
    deep_link: Optional[str] = None
    test_type: Literal["analyze", "e2e"] = "analyze"
    device: Optional[MobileDevice] = None
    project: Optional[str] = None


class JobEnqueueResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    kind: str
    result_path: Optional[str] = None
    error: Optional[str] = None


# ---------- App ----------
app = FastAPI(title="RateMate TaaS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _write_status(job_id: str, payload: dict, status: str, kind: str) -> Path:
    out = {
        "job_id": job_id,
        "status": status,
        "kind": kind,
        "payload": payload,
    }
    path = RESULTS_DIR / f"{job_id}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


@app.post("/api/test/web", response_model=JobEnqueueResponse)
def enqueue_web(req: WebTestRequest, _: bool = Depends(verify_api_key)):
    job_id = uuid.uuid4().hex
    # Ensure JSON-serializable payload (e.g., AnyUrl -> str)
    payload = req.model_dump(mode="json")
    _write_status(job_id, payload, status="queued", kind="web")
    q = get_queue()
    # Enqueue worker task name; worker container must import tasks.run_web_test
    q.enqueue("tasks.run_web_test", job_id, payload, job_id=job_id)
    return JobEnqueueResponse(job_id=job_id, status="queued")


@app.post("/api/test/mobile", response_model=JobEnqueueResponse)
def enqueue_mobile(req: MobileTestRequest, _: bool = Depends(verify_api_key)):
    job_id = uuid.uuid4().hex
    payload = req.model_dump(mode="json")
    _write_status(job_id, payload, status="queued", kind="mobile")
    q = get_queue()
    q.enqueue("tasks.run_mobile_test", job_id, payload, job_id=job_id)
    return JobEnqueueResponse(job_id=job_id, status="queued")


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, _: bool = Depends(verify_api_key)):
    path = RESULTS_DIR / f"{job_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Job not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return JobStatusResponse(
        job_id=str(data.get("job_id") or job_id),
        status=str(data.get("status") or "unknown"),
        kind=str(data.get("kind") or "unknown"),
        result_path=str(data.get("result_path") or ""),
        error=data.get("error"),
    )


@app.get("/healthz")
def healthz():
    try:
        _ = _redis_conn().ping()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
