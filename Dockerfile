# Image chính chủ Playwright đã kèm browsers đúng version
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CI=1 \
    # Tránh tải lại browsers và tăng heap cho Node (driver của Playwright)
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NODE_OPTIONS=--max-old-space-size=6144

WORKDIR /app

# Cài deps Python
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Tạo sẵn thư mục report/output
RUN mkdir -p /app/report /tmp/pytest_cache /tmp/test-results

# Copy mã nguồn
COPY . /app

# Chạy root để dễ docker cp báo cáo
USER root

# Mặc định chạy Chromium, tắt tracing để nhẹ bộ nhớ
ENTRYPOINT ["bash","-lc"]
CMD ["pytest -vv -s tests/auth tests/smoke/test_routes.py \
  --browser=chromium \
  -p no:pytest_excel \
  -o cache_dir=/tmp/pytest_cache \
  --output=/tmp/test-results \
  --screenshot=only-on-failure --video=off --tracing=off \
  -o junit_family=xunit2 --junitxml=/app/report/junit.xml \
  --html=/app/report/e2e.html --self-contained-html \
  -o log_cli=true -o log_cli_level=INFO --durations=10"]
