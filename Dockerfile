# Dùng image chính thức của Playwright có sẵn Chromium/Firefox/WebKit & deps
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    CI=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Cài deps Python trước để tận dụng layer cache
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

# Copy source
COPY . /app

# (Browsers đã có sẵn trong base image)
# Entry mặc định – trong CI sẽ override bằng lệnh `bash -lc '...'`
CMD ["pytest", "-vv", "tests", "--browser=chromium", "--screenshot=only-on-failure", "--video=off", "--tracing=retain-on-failure"]
