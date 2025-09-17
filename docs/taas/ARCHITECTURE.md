# RateMate TaaS – Kiến trúc & Lộ trình

Mục tiêu: Nâng cấp suite E2E hiện tại thành một nền tảng Testing‑as‑a‑Service (TaaS) có API/Gateway, hàng đợi, worker và dashboard.

## Tổng quan

- Gateway (FastAPI) phơi API `/api/test/web`, `/api/test/mobile`, `/api/jobs/{id}`
- Message Queue: Redis + RQ (đơn giản, dễ vận hành)
- Workers: Python RQ worker xử lý job và ghi kết quả JSON
- Lưu kết quả: thư mục `test-results/taas/` (có thể thay bằng S3 sau)
- Bảo mật: API key qua header `x-api-key`

```
[Frontend] → [API Gateway] → [Redis Queue] ← [RQ Worker] → [Kết quả]
                                └────────→ [Test Engines: Playwright / Lighthouse / Appium / MobSF]
```

## Mô-đun & tích hợp

- Web Testing: sau này gọi Playwright (smoke/full), Lighthouse (performance), OWASP ZAP (security)
- Mobile Testing: sau này gọi MobSF (analyze) và Appium hoặc Firebase Test Lab (e2e)

## Triển khai nhanh (MVP)

1) `docker compose -f docker-compose.taas.yml up --build`
2) Gọi API:
   - `POST /api/test/web` body: `{ "url": "https://example.com", "test_type": "smoke" }`
   - `POST /api/test/mobile` body: `{ "apk_url": "https://...", "test_type": "analyze" }`
   - `GET  /api/jobs/{job_id}` để xem trạng thái

Đặt header: `x-api-key: dev-key` (hoặc override `API_KEY` trong env)

## Lộ trình mở rộng

- Tách service chi tiết: web-testing, mobile-testing, report-service
- Lưu trữ artifacts (ảnh/video/log) lên S3, lưu metadata vào Postgres
- Frontend dashboard (Next.js/React) đọc API để hiển thị Test Run History
- Tích hợp CI/CD: publish API token và gọi `POST /api/test/...` sau mỗi build
- Auto-scaling: chuyển từ docker-compose sang Kubernetes + HPA

## Lược đồ DB (đề xuất)

- Projects(id, name, type)
- TestSessions(id, project_id, status, start_time, end_time, kind)
- WebResults(session_id, lighthouse_score, zap_alerts)
- MobileResults(session_id, device_name, os_version, app_permissions)

