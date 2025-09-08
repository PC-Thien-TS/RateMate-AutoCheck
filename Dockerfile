# Dockerfile — Playwright base image khớp 1.47.0 (có sẵn browsers)
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CI=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NODE_OPTIONS="--max-old-space-size=2048"

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN mkdir -p /app/report /tmp/pytest_cache /tmp/test-results
COPY . /app

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
