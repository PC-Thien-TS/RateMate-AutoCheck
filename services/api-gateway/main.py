import os
import uuid
import json
from pathlib import Path
from typing import Optional, Literal, List

from fastapi import FastAPI, Depends, Header, HTTPException, status, UploadFile, File, Query
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AnyUrl
from fastapi.responses import RedirectResponse
from rq import Queue
from redis import Redis
import db as dbmod


# ---------- Config ----------
RESULTS_DIR = Path(os.getenv("TAAS_RESULTS_DIR", "test-results/taas")).resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(os.getenv("TAAS_UPLOAD_DIR", str(RESULTS_DIR / "uploads"))).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
    url: Optional[AnyUrl] = None
    test_type: Literal["smoke", "full", "performance", "security", "auto"] = "smoke"
    site: Optional[str] = None
    routes: Optional[List[str]] = None


class MobileDevice(BaseModel):
    name: Optional[str] = None
    platform: Literal["android", "ios"] = "android"
    os_version: Optional[str] = None
    is_emulator: Optional[bool] = True


class MobileTestRequest(BaseModel):
    apk_url: Optional[str] = None
    ipa_url: Optional[str] = None
    apk_path: Optional[str] = None
    ipa_path: Optional[str] = None
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
    payload: Optional[dict] = None
    artifact_urls: Optional[dict] = None


# ---------- App ----------
app = FastAPI(title="RateMate TaaS API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "name": "RateMate TaaS API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": [
            {"method": "POST", "path": "/api/test/web"},
            {"method": "POST", "path": "/api/test/mobile"},
            {"method": "POST", "path": "/api/upload/mobile"},
            {"method": "GET", "path": "/api/jobs/{job_id}"},
            {"method": "GET", "path": "/healthz"},
        ],
    }


@app.on_event("startup")
def _startup():
    try:
        dbmod.ensure_schema()
    except Exception:
        pass


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
    try:
        dbmod.insert_session(job_id, kind="web", test_type=req.test_type, project=req.site or None, status="queued")
    except Exception:
        pass
    q = get_queue()
    # Enqueue worker task name; worker container must import tasks.run_web_test
    q.enqueue("tasks.run_web_test", job_id, payload, job_id=job_id)
    return JobEnqueueResponse(job_id=job_id, status="queued")


@app.post("/api/test/mobile", response_model=JobEnqueueResponse)
def enqueue_mobile(req: MobileTestRequest, _: bool = Depends(verify_api_key)):
    job_id = uuid.uuid4().hex
    payload = req.model_dump(mode="json")
    _write_status(job_id, payload, status="queued", kind="mobile")
    try:
        dbmod.insert_session(job_id, kind="mobile", test_type=req.test_type, project=req.project or None, status="queued")
    except Exception:
        pass
    q = get_queue()
    q.enqueue("tasks.run_mobile_test", job_id, payload, job_id=job_id)
    return JobEnqueueResponse(job_id=job_id, status="queued")


@app.post("/api/upload/mobile")
def upload_mobile(file: UploadFile = File(...), _: bool = Depends(verify_api_key)):
    try:
        suffix = Path(file.filename or "upload.bin").suffix.lower()
        name = f"{uuid.uuid4().hex}{suffix}"
        dst = UPLOAD_DIR / name
        with dst.open("wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return {"path": str(dst), "filename": file.filename, "size": dst.stat().st_size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        payload=data.get("payload") if isinstance(data.get("payload"), dict) else None,
        artifact_urls=data.get("artifact_urls") if isinstance(data.get("artifact_urls"), dict) else None,
    )


@app.get("/healthz")
def healthz():
    try:
        _ = _redis_conn().ping()
        # Try a lightweight DB query
        try:
            dbmod.ensure_schema()
            db_ok = True
        except Exception:
            db_ok = False
        return {"ok": True, "db": db_ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/artifacts/{job_id}/{name}")
def get_artifact(job_id: str, name: str, _: bool = Depends(verify_api_key)):
    """Redirect to the presigned URL stored in job status JSON.
    This acts as a simple download/stream endpoint for dashboard/CI.
    """
    path = RESULTS_DIR / f"{job_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Job not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    arts = data.get("artifact_urls") or {}
    info = arts.get(name)
    if isinstance(info, dict) and info.get("presigned_url"):
        return RedirectResponse(url=str(info["presigned_url"]))
    raise HTTPException(status_code=404, detail="Artifact not found")


# -------- Sessions API (for dashboard) --------

@app.get("/api/sessions")
def list_sessions(
    _: bool = Depends(verify_api_key),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    project: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    test_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
):
    try:
        rows = dbmod.list_sessions(limit=limit, offset=offset, project=project, kind=kind, status=status, test_type=test_type, since=since, until=until)
        return {"items": rows, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, _: bool = Depends(verify_api_key)):
    sess = dbmod.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    res = None
    try:
        res = dbmod.latest_result(session_id)
    except Exception:
        res = None
    return {"session": sess, "latest_result": res}


@app.get("/api/sessions/{session_id}/results")
def list_session_results(session_id: str, _: bool = Depends(verify_api_key), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    try:
        rows = dbmod.list_results(session_id, limit=limit, offset=offset)
        return {"items": rows, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results/{result_id}")
def get_result(result_id: int, _: bool = Depends(verify_api_key)):
    row = dbmod.get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row


def _extract_alerts(obj: dict) -> list:
    try:
        sec = obj.get("summary", {}).get("security") if "summary" in obj else obj.get("security")
        alerts = sec.get("alerts") if isinstance(sec, dict) else None
        return alerts if isinstance(alerts, list) else []
    except Exception:
        return []


@app.get("/api/results/{result_id}/alerts.json")
def result_alerts_json(result_id: int, _: bool = Depends(verify_api_key)):
    row = dbmod.get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    al = _extract_alerts(row) or []
    return JSONResponse(content={"result_id": result_id, "count": len(al), "alerts": al})


@app.get("/api/results/{result_id}/alerts.csv")
def result_alerts_csv(result_id: int, _: bool = Depends(verify_api_key)):
    row = dbmod.get_result(result_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    alerts = _extract_alerts(row)
    cols = ["risk", "alert", "url", "evidence"]
    # simple CSV
    lines = [",".join(cols)]
    def esc(s):
        if s is None:
            return ""
        t = str(s).replace('"','""')
        return f'"{t}"'
    for a in alerts:
        lines.append(
            ",".join(esc(a.get(c)) for c in cols)
        )
    csv = "\n".join(lines) + "\n"
    return Response(content=csv, media_type="text/csv")


@app.get("/api/sessions/{session_id}/alerts.json")
def session_latest_alerts_json(session_id: str, _: bool = Depends(verify_api_key)):
    res = dbmod.latest_result(session_id)
    if not res:
        raise HTTPException(status_code=404, detail="No results")
    al = _extract_alerts(res) or []
    return JSONResponse(content={"session_id": session_id, "result_id": res.get("id"), "count": len(al), "alerts": al})


@app.get("/api/sessions/{session_id}/alerts.csv")
def session_latest_alerts_csv(session_id: str, _: bool = Depends(verify_api_key)):
    res = dbmod.latest_result(session_id)
    if not res:
        raise HTTPException(status_code=404, detail="No results")
    alerts = _extract_alerts(res)
    cols = ["risk", "alert", "url", "evidence"]
    lines = [",".join(cols)]
    def esc(s):
        if s is None:
            return ""
        t = str(s).replace('"','""')
        return f'"{t}"'
    for a in alerts:
        lines.append(
            ",".join(esc(a.get(c)) for c in cols)
        )
    csv = "\n".join(lines) + "\n"
    return Response(content=csv, media_type="text/csv")
