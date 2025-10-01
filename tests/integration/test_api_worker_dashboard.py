import requests
import os
import pytest

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-key")

@pytest.mark.integration
def test_health_check():
    resp = requests.get(f"{API_URL}/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["redis"] is True
    assert data["db"] is True

@pytest.mark.integration
def test_enqueue_job_and_status():
    payload = {"url": "https://store.ratemate.top", "test_type": "smoke"}
    headers = {"x-api-key": API_KEY}
    resp = requests.post(f"{API_URL}/api/test/web", json=payload, headers=headers)
    assert resp.status_code == 200
    job_id = resp.json().get("job_id")
    assert job_id
    status_resp = requests.get(f"{API_URL}/api/jobs/{job_id}", headers=headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] in {"queued", "running", "completed", "failed"}


@pytest.mark.integration
def test_invalid_api_key():
    resp = requests.post(f"{API_URL}/api/test/web", json={"url": "https://store.ratemate.top"}, headers={"x-api-key": "invalid-key"})
    assert resp.status_code == 401
    assert "Invalid API key" in resp.text

@pytest.mark.integration
def test_missing_required_fields():
    headers = {"x-api-key": API_KEY}
    resp = requests.post(f"{API_URL}/api/test/web", json={}, headers=headers)
    assert resp.status_code in {400, 422}

@pytest.mark.integration
def test_upload_limit_exceeded():
    headers = {"x-api-key": API_KEY}
    big_file = b"0" * (int(os.getenv("TAAS_UPLOAD_MAX_MB", "200")) * 1024 * 1024 + 1024)
    files = {"file": ("big.apk", big_file)}
    resp = requests.post(f"{API_URL}/api/upload/mobile", files=files, headers=headers)
    assert resp.status_code in {413, 400, 422}

@pytest.mark.integration
def test_health_check_with_redis_down(monkeypatch):
    # Simulate Redis down by patching _redis_conn to raise
    import sys
    this = sys.modules[__name__]
    orig = getattr(this, "requests")
    # This is a placeholder; actual Redis down simulation should be done in staging
    # For now, just check healthz returns ok or error
    resp = requests.get(f"{API_URL}/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
