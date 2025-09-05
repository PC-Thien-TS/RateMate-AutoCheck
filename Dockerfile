# Playwright image đã kèm browsers, phiên bản ổn định (1.46.1)
FROM mcr.microsoft.com/playwright/python:v1.46.1-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CI=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PWDEBUG=0

WORKDIR /app

# Cài deps Python (đã ghim version khớp image)
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Thư mục báo cáo
RUN mkdir -p /app/report /tmp/pytest_cache /tmp/test-results

# Copy source
COPY . /app

# Chạy root để dễ docker cp báo cáo
USER root

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