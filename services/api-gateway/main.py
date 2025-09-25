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
import boto3
from botocore.client import Config
import urllib.parse
from rq import Queue
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
from redis import Redis
import db as dbmod


# ---------- Config ----------
RESULTS_DIR = Path(os.getenv("TAAS_RESULTS_DIR", "test-results/taas")).resolve()
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(os.getenv("TAAS_UPLOAD_DIR", str(RESULTS_DIR / "uploads"))).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_MAX_MB = None
try:
    _upload_mb_raw = os.getenv("TAAS_UPLOAD_MAX_MB")
    if _upload_mb_raw not in (None, ""):
        UPLOAD_MAX_MB = max(0, int(float(_upload_mb_raw)))
    else:
        UPLOAD_MAX_MB = 200
except Exception:
    UPLOAD_MAX_MB = 200
UPLOAD_MAX_BYTES = (UPLOAD_MAX_MB or 0) * 1024 * 1024


def _parse_allowed_exts(raw: str | None) -> set[str]:
    default = {".apk", ".aab", ".ipa", ".zip"}
    if not raw:
        return default
    out = {f".{ext.strip().lstrip('.').lower()}" for ext in raw.split(',') if ext.strip()}
    return out or default

UPLOAD_ALLOWED_EXTS = _parse_allowed_exts(os.getenv("TAAS_UPLOAD_ALLOWED_EXTS"))
UPLOAD_CHUNK_BYTES = 1024 * 1024

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("TAAS_QUEUE_NAME", "taas")
API_KEY = os.getenv("API_KEY", "dev-key")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
_CORS_RAW = os.getenv("TAAS_CORS_ORIGINS") or os.getenv("CORS_ALLOW_ORIGINS") or "*"

def _parse_origins(raw: str) -> list[str]:
    try:
        parts = [p.strip() for p in str(raw).split(",") if str(p).strip()]
        if not parts or "*" in parts:
            return ["*"]
        return parts
    except Exception:
        return ["*"]

# S3/MinIO config (for baseline acceptance)
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_PUBLIC_ENDPOINT = os.getenv("S3_PUBLIC_ENDPOINT") or S3_ENDPOINT
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "taas-artifacts")
S3_REGION = os.getenv("S3_REGION", "us-east-1")


def _redis_conn() -> Redis:
    return Redis.from_url(REDIS_URL)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_redis_conn())


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    api_key_query: Optional[str] = Query(default=None, alias="api_key"),
):
    # Accept either legacy global API_KEY or DB-backed api_keys
    provided = x_api_key or api_key_query
    if API_KEY and provided == API_KEY:
        return True
    # DB verify + basic rate limit per key
    try:
        rec = dbmod.verify_api_key(provided or "")
    except Exception:
        rec = None
    if not rec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    # Rate limit (per minute) using Redis
    try:
        limit = int(rec.get("rate_limit_per_min") or 60)
        if limit > 0:
            minute = int(__import__('time').time() // 60)
            key = f"rl:{rec['id']}:{minute}"
            val = _redis_conn().incr(key)
            if val == 1:
                _redis_conn().expire(key, 60)
            if val > limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except HTTPException:
        raise
    except Exception:
        pass
    return True


# ---------- Models ----------
class WebTestRequest(BaseModel):
    url: Optional[AnyUrl] = None
    test_type: Literal["smoke", "full", "performance", "security", "auto"] = "smoke"
    site: Optional[str] = None
    routes: Optional[List[str]] = None
    project: Optional[str] = None


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
    allow_origins=_parse_origins(_CORS_RAW),
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
        dbmod.insert_session(job_id, kind="web", test_type=req.test_type, project=(req.project or req.site) or None, status="queued")
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
    dst: Path | None = None
    try:
        original_name = file.filename or "upload.bin"
        suffix = Path(original_name).suffix.lower()
        if suffix not in UPLOAD_ALLOWED_EXTS:
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Unsupported file type: {suffix or 'unknown'}")
        name = f"{uuid.uuid4().hex}{suffix}"
        dst = UPLOAD_DIR / name
        total = 0
        with dst.open("wb") as fh:
            while True:
                chunk = file.file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if UPLOAD_MAX_BYTES and total > UPLOAD_MAX_BYTES:
                    limit_mb = UPLOAD_MAX_MB or int(UPLOAD_MAX_BYTES / (1024 * 1024))
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"File too large (>{limit_mb} MB)")
                fh.write(chunk)
        return {"path": str(dst), "filename": original_name, "size": total}
    except HTTPException:
        if dst and dst.exists():
            dst.unlink(missing_ok=True)
        raise
    except Exception as e:
        if dst and dst.exists():
            dst.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            file.file.close()
        except Exception:
            pass


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, _: bool = Depends(verify_api_key)):
    """Return job status from status file; fallback to DB + results if missing.

    In some deployments, the ephemeral status file may be cleaned up or lost
    after container restarts. This endpoint now gracefully falls back to
    Postgres to provide a best-effort status and artifact URLs from the latest
    result summary when the file is absent.
    """
    path = RESULTS_DIR / f"{job_id}.json"
    if path.is_file():
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

    # Fallback: use DB info and any artifact URLs from latest result
    try:
        sess = dbmod.get_session(job_id)
    except Exception:
        sess = None
    if not sess:
        raise HTTPException(status_code=404, detail="Job not found")
    # Try to locate result JSON and artifact URLs from DB summary
    result_path = str((RESULTS_DIR / f"{job_id}-result.json"))
    arts = None
    try:
        res = dbmod.latest_result(job_id)
        if res and isinstance(res.get("summary"), dict):
            sm = res["summary"]
            if isinstance(sm.get("artifact_urls"), dict):
                arts = sm["artifact_urls"]
    except Exception:
        pass
    return JobStatusResponse(
        job_id=job_id,
        status=str(sess.get("status") or "unknown"),
        kind=str(sess.get("kind") or "unknown"),
        result_path=result_path if (RESULTS_DIR / f"{job_id}-result.json").is_file() else "",
        error=None,
        payload=None,
        artifact_urls=arts if isinstance(arts, dict) else None,
    )


@app.get("/healthz")
def healthz():
    try:
        _ = _redis_conn().ping()
        redis_ok = True
    except Exception as e:
        return {"ok": False, "redis": False, "error": str(e)}
    # Try a lightweight DB query
    try:
        dbmod.ensure_schema()
        db_ok = True
    except Exception:
        db_ok = False
    s3_cfg = bool(S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY)
    return {"ok": True, "redis": redis_ok, "db": db_ok, "s3_configured": s3_cfg}


@app.get("/api/stats")
def stats(_: bool = Depends(verify_api_key)):
    try:
        q = get_queue()
        conn = _redis_conn()
        started = StartedJobRegistry(q.name, connection=conn)
        finished = FinishedJobRegistry(q.name, connection=conn)
        failed = FailedJobRegistry(q.name, connection=conn)
        return {
            "queue": q.name,
            "queued": q.count,
            "started": len(started),
            "finished": len(finished),
            "failed": len(failed),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, _: bool = Depends(verify_api_key)):
    # cooperative cancel: mark a Redis key that workers check
    conn = _redis_conn()
    conn.setex(f"cancel:{job_id}", 3600, "1")
    # reflect in status file
    path = RESULTS_DIR / f"{job_id}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {"job_id": job_id}
    else:
        data = {"job_id": job_id}
    data["status"] = "cancel_requested"
    (RESULTS_DIR / f"{job_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@app.post("/api/jobs/{job_id}/retry", response_model=JobEnqueueResponse)
def retry_job(job_id: str, _: bool = Depends(verify_api_key)):
    path = RESULTS_DIR / f"{job_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Job not found")
    data = json.loads(path.read_text(encoding="utf-8")) or {}
    payload = data.get("payload") or {}
    kind = str(data.get("kind") or "web")
    new_id = uuid.uuid4().hex
    _write_status(new_id, payload, status="queued", kind=kind)
    q = get_queue()
    target = "tasks.run_mobile_test" if kind == "mobile" else "tasks.run_web_test"
    q.enqueue(target, new_id, payload, job_id=new_id)
    return JobEnqueueResponse(job_id=new_id, status="queued")


@app.get("/api/job-results/{job_id}")
def get_job_results(job_id: str, _: bool = Depends(verify_api_key)):
    rp = RESULTS_DIR / f"{job_id}-result.json"
    if not rp.is_file():
        raise HTTPException(status_code=404, detail="Result not found")
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _s3_client():
    if not (S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY):
        raise HTTPException(status_code=500, detail="S3 not configured")
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version='s3v4'),
    )

def _s3_public_client():
    if not (S3_PUBLIC_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY):
        return _s3_client()
    return boto3.client(
        's3',
        endpoint_url=S3_PUBLIC_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version='s3v4'),
    )


def _slug_from_url(u: str) -> str:
    try:
        p = urllib.parse.urlparse(u)
        path = p.path or "/"
        s = path.replace("/", "_")
        s = s.strip("_") or "root"
        return s
    except Exception:
        return "route"


@app.post("/api/visual/accept")
def visual_accept(data: dict, _: bool = Depends(verify_api_key)):
    job_id = str(data.get("job_id") or "").strip()
    index = int(data.get("index") or 1)
    project = (str(data.get("project") or "").strip()) or None
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id required")

    # Load job result to get URL + project if needed
    res = get_job_results(job_id, True)
    test_type = (res.get("test_type") or "").lower()
    cases = res.get("cases") if isinstance(res.get("cases"), list) else None
    if cases:
        try:
            url = cases[index-1].get("url")
        except Exception:
            url = None
    else:
        url = res.get("url")
    if not project:
        # from payload in status JSON
        st = json.loads((RESULTS_DIR / f"{job_id}.json").read_text(encoding="utf-8"))
        pl = st.get("payload", {}) if isinstance(st, dict) else {}
        project = pl.get("project") or pl.get("site") or "default"

    # Determine screenshot path
    sp = RESULTS_DIR / f"{job_id}-{index}-screenshot.png"
    if not sp.is_file():
        # fallback single screenshot name
        sp = RESULTS_DIR / f"{job_id}-screenshot.png"
    if not sp.is_file():
        raise HTTPException(status_code=404, detail="screenshot not found")

    # Compute baseline key and upload
    slug = _slug_from_url(url or f"case-{index}")
    dim = "1366x900"
    key = f"baselines/{project}/{slug}_{dim}.png"
    cli = _s3_client()
    try:
        cli.upload_file(str(sp), S3_BUCKET, key)
        ttl = int(os.getenv('ARTIFACT_TTL_SECONDS', '86400'))
        pres = _s3_public_client() or cli
        url_signed = pres.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': key}, ExpiresIn=ttl)
        return {"ok": True, "baseline_key": key, "url": url_signed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/artifacts/{job_id}/{name}")
def get_artifact(job_id: str, name: str, _: bool = Depends(verify_api_key)):
    """Redirect to the presigned URL stored in job status JSON.
    This acts as a simple download/stream endpoint for dashboard/CI.
    """
    # Try status file first
    info = None
    path = RESULTS_DIR / f"{job_id}.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            arts = data.get("artifact_urls") or {}
            info = arts.get(name)
        except Exception:
            info = None
    # Fallback to DB summary
    if not info:
        try:
            res = dbmod.latest_result(job_id)
            if res and isinstance(res.get("summary"), dict):
                arts = res["summary"].get("artifact_urls") or {}
                info = arts.get(name)
        except Exception:
            info = None
    # If we have bucket/key, (re)sign on the fly using public endpoint to avoid stale signatures
    if isinstance(info, dict):
        bucket = info.get("bucket") or S3_BUCKET
        key = info.get("key")
        if not key:
            # Try to find from DB summary
            try:
                res = dbmod.latest_result(job_id)
                if res and isinstance(res.get("summary"), dict):
                    arts2 = res["summary"].get("artifact_urls") or {}
                    info2 = arts2.get(name)
                    if isinstance(info2, dict):
                        bucket = info2.get("bucket") or bucket
                        key = info2.get("key") or key
            except Exception:
                pass
        if key:
            try:
                cli = _s3_public_client()
                ttl = int(os.getenv('ARTIFACT_TTL_SECONDS', '86400'))
                # Force inline display for common image types
                ext = (Path(key).suffix or '').lower()
                params = {'Bucket': bucket, 'Key': key}
                if ext in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}:
                    ctype = 'image/jpeg' if ext in {'.jpg', '.jpeg'} else f"image/{ext.lstrip('.')}"
                    params['ResponseContentDisposition'] = 'inline'
                    params['ResponseContentType'] = ctype
                url = cli.generate_presigned_url('get_object', Params=params, ExpiresIn=ttl)
                return RedirectResponse(url=str(url))
            except Exception:
                pass
        if info.get("presigned_url"):
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


# -------- Admin: API Keys --------

def _verify_admin(x_admin_token: Optional[str] = Header(default=None)):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


@app.get("/api/admin/keys")
def admin_list_keys(_: bool = Depends(_verify_admin)):
    try:
        return {"items": dbmod.list_api_keys()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/keys")
def admin_create_key(data: dict, _: bool = Depends(_verify_admin)):
    name = str(data.get("name") or "token")
    project = data.get("project")
    rate = int(data.get("rate_limit_per_min") or 60)
    # Generate random token
    raw = uuid.uuid4().hex + uuid.uuid4().hex
    rec = dbmod.insert_api_key(name=name, project=project, raw_key=raw, rate_limit_per_min=rate)
    rec["api_key"] = raw
    return rec


@app.patch("/api/admin/keys/{key_id}")
def admin_update_key(key_id: int, data: dict, _: bool = Depends(_verify_admin)):
    active = data.get("active")
    rate = data.get("rate_limit_per_min")
    try:
        row = dbmod.update_api_key(key_id, active=active if active is not None else None, rate_limit_per_min=int(rate) if rate is not None else None)
        if not row:
            raise HTTPException(status_code=404, detail="Key not found")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects")
def list_projects(_: bool = Depends(verify_api_key)):
    try:
        return {"items": dbmod.list_projects()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
