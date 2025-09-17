# RateMate TaaS API

Base URL: `http://localhost:8000`

Auth: Header `x-api-key: <API_KEY>` (mặc định `dev-key` trong compose)

## POST /api/test/web

Body

```
{
  "url": "https://store.ratemate.top",              // optional nếu dùng site config
  "test_type": "smoke" | "full" | "performance" | "security",
  "site": "ratemate",                                // optional
  "routes": ["/en/login","/en/store"]              // optional (multi‑route)
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

## POST /api/upload/mobile

Multipart form-data with key `file` (apk/ipa). Returns `{ path, filename, size }`.

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

Ghi chú: MVP chỉ sinh JSON giả lập cho performance/security/mobile‑e2e. Các phần tích hợp thật sẽ ghi logs, ảnh, video.

## Gợi ý dùng site config (multi‑route)

Tạo file `config/sites/ratemate.yml`:

```
base_url: "https://store.ratemate.top"
routes:
  public: ["/en/login","/en/store"]
# assertions (tùy chọn) – CSS selector cho từng route
# assertions:
#   "/en/login":
#     - 'input[type="email"]'
#     - 'input[type="password"]'
```

- Gửi `{ "site": "ratemate", "test_type": "smoke" }` để worker tự lấy base_url + routes.
- Nếu truyền `routes` mà không có file site, hãy cung cấp `url` làm base.

