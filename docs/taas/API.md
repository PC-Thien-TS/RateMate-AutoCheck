# RateMate TaaS API

Base URL: `http://localhost:8000`

Auth: Header `x-api-key: <API_KEY>` (mặc định `dev-key` trong compose)

## POST /api/test/web

Body

```
{
  "url": "https://store.ratemate.top",
  "test_type": "smoke" | "full" | "performance" | "security",
  "site": "ratemate" // optional
}
```

Resp

```
{ "job_id": "<uuid>", "status": "queued" }
```

## POST /api/test/mobile

Body

```
{
  "apk_url": "https://...", // hoặc ipa_url hoặc deep_link
  "test_type": "analyze" | "e2e",
  "device": { "platform": "android" | "ios", "os_version": "13" }
}
```

Resp: giống web

## GET /api/jobs/{job_id}

Resp

```
{
  "job_id": "...",
  "status": "queued|running|completed|failed",
  "kind": "web|mobile",
  "result_path": "test-results/taas/<job>-result.json"
}
```

Ghi chú: MVP chỉ sinh JSON giả lập. Tích hợp thật sẽ ghi logs, ảnh, video.

