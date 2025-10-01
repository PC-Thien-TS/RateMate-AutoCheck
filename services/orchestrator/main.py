import os
from typing import List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="RateMate TaaS Orchestrator", version="0.1.0")

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000").rstrip("/")
API_GATEWAY_KEY = os.getenv("API_GATEWAY_API_KEY", os.getenv("API_KEY", ""))
DEFAULT_TIMEOUT = float(os.getenv("ORCHESTRATOR_HTTP_TIMEOUT", "30"))


class PlanTestsRequest(BaseModel):
    project: Optional[str] = None
    targets: List[Literal["web", "mobile"]] = Field(default_factory=lambda: ["web"])
    spec_md: Optional[str] = None


class PlanTestsResponse(BaseModel):
    plan_markdown: str
    notes: Optional[str] = None


class GenerateTestsRequest(BaseModel):
    repo_root: str
    target: Literal["web", "mobile", "both"] = "web"
    spec_md: Optional[str] = None


class GenerateTestsResponse(BaseModel):
    patch: str
    summary: Optional[str] = None


class RunTestsRequest(BaseModel):
    kind: Literal["web", "mobile"] = "web"
    payload: dict = Field(default_factory=dict)


class RunTestsResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    detail: Optional[dict] = None


def _gateway_headers() -> dict:
    headers: dict[str, str] = {}
    if API_GATEWAY_KEY:
        headers["x-api-key"] = API_GATEWAY_KEY
    return headers


@app.post("/plan-tests", response_model=PlanTestsResponse)
async def plan_tests(req: PlanTestsRequest) -> PlanTestsResponse:
    # Placeholder implementation; integrate LLM workflow here.
    project = req.project or "application"
    targets = ", ".join(req.targets)
    outline = [
        f"# Test Plan for {project}",
        "",
        f"Targets: {targets}",
        "- Smoke routes",
        "- Authentication flows",
        "- Visual regression",
        "- Performance & Security (optional)",
    ]
    return PlanTestsResponse(plan_markdown="\n".join(outline), notes="AI planning not yet implemented")


@app.post("/generate-tests", response_model=GenerateTestsResponse)
async def generate_tests(req: GenerateTestsRequest) -> GenerateTestsResponse:
    # Placeholder diff to unblock wiring with VS Code extension.
    placeholder = (
        "--- a/tests/example_test.py\n"
        "+++ b/tests/example_test.py\n"
        "@@\n"
        "+def test_placeholder():\n"
        "+    assert True\n"
    )
    return GenerateTestsResponse(patch=placeholder, summary="Replace with LLM-generated test suite")


@app.post("/run-tests", response_model=RunTestsResponse)
async def run_tests(req: RunTestsRequest) -> RunTestsResponse:
    endpoint = "/api/test/web" if req.kind == "web" else "/api/test/mobile"
    url = f"{API_GATEWAY_URL}{endpoint}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.post(url, json=req.payload, headers=_gateway_headers())
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json()
    return RunTestsResponse(job_id=data.get("job_id", ""), status=data.get("status", "queued"))


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def job_status(job_id: str) -> JobStatusResponse:
    url = f"{API_GATEWAY_URL}/api/jobs/{job_id}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.get(url, headers=_gateway_headers())
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    data = response.json()
    return JobStatusResponse(job_id=data.get("job_id", job_id), status=data.get("status", "unknown"), detail=data)


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "api_gateway_url": API_GATEWAY_URL}
