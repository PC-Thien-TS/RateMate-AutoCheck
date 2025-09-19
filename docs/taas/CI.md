# CI/CD Integration (GitHub Actions)

This workflow calls the TaaS API to enqueue tests and polls until completion.

1) Add repository secrets
- `TAAS_API_URL` (e.g., https://taas.example.com)
- `TAAS_API_KEY` (the x-api-key configured on the server)

2) Trigger workflow
- From Actions → “TaaS E2E” → Run workflow
- Inputs:
  - kind: `web` or `mobile`
  - test_type: `smoke|performance|security|auto` (or `analyze` for mobile)
  - url/site/routes for web; apk_url for mobile analyze

3) Behavior
- Enqueues the job (`POST /api/test/{web|mobile}`) using provided inputs
- Polls `GET /api/jobs/{job_id}` until status != queued|running (timeout 15m)
- Fails the workflow if status != completed
- Uploads `job-status.json` as an artifact (the full JSON from the API)

Notes
- Hosted runners must reach your API over the internet. For on-prem/private APIs, use a self-hosted runner.
- To integrate with your delivery pipeline, add this workflow as a required check and wire thresholds via env on the server.

