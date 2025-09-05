# Dockerfile — dùng image chính chủ đã kèm đủ browsers cho Playwright 1.47.0
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

WORKDIR /app

# Cài deps Python trước để cache tốt
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r requirements.txt

# (Tùy chọn) Đảm bảo browsers khớp đúng build hiện tại
# Base image đã có sẵn; lệnh dưới chỉ để idempotent trong mọi môi trường
RUN python -m playwright install --with-deps chromium firefox webkit

# Copy source
COPY . /app

# Giữ nguyên entrypoint chạy pytest từ workflow, không ép user trong Dockerfile
# Entry mặc định – trong CI sẽ override bằng lệnh `bash -lc '...'`
CMD ["pytest", "-vv", "tests", "--browser=chromium", "--screenshot=only-on-failure", "--video=off", "--tracing=retain-on-failure"]
