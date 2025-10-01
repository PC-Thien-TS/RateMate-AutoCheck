# Orchestrator Service

Lightweight FastAPI service that coordinates AI agents and bridges VS Code tooling with the existing RateMate TaaS backend.

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8088
```

Environment variables:

- `API_GATEWAY_URL` (default `http://api-gateway:8000`)
- `API_GATEWAY_API_KEY` (optional service-to-service key)
- `ORCHESTRATOR_HTTP_TIMEOUT` (seconds, default 30)
- `DASH_SESSION_SECRET` (shared with dashboard if orchestrator needs cookie verification later)

Endpoints are currently stubs; integrate LangChain/AutoGen flows inside `/plan-tests` and `/generate-tests`.
