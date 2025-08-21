# Auto-Check-Web

[![E2E](https://github.com/PCThien-Ek/RateMate-AutoCheck/actions/workflows/e2e.yml/badge.svg?branch=main)](https://github.com/PCThien-Ek/RateMate-AutoCheck/actions/workflows/e2e.yml)

## Yêu cầu
- Docker (bắt buộc)
- Make (tùy chọn, cho Linux/macOS/WSL; Windows có `make.ps1`)

## Chuẩn bị
```bash
cp .env.example .env   # mở .env và điền BASE_URL_PROD, LOGIN_EMAIL, LOGIN_PASSWORD, ...

## CI/CD

- Workflow: `.github/workflows/e2e.yml`
- Artifact báo cáo Excel được giữ **14 ngày**.
- Khuyến nghị bảo vệ nhánh `main`: Require status check **“E2E”** trước khi merge.
