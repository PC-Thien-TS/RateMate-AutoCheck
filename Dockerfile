# Dockerfile — Image chạy đủ Chromium/Firefox/WebKit cho Playwright
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# APT base + system deps cho browsers (retry & fallback)
RUN set -eux; \
    echo 'Acquire::Retries "5"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' >/etc/apt/apt.conf.d/80retry; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl git tzdata \
      python3 python3-pip python3-venv; \
    apt-get install -y --no-install-recommends \
      libasound2 \
      libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
      libcups2 libdbus-1-3 libdrm2 libgbm1 \
      libglib2.0-0 libgtk-3-0 libnss3 libnspr4 \
      libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
      libxrandr2 libxkbcommon0 libxshmfence1 libxext6 libxfixes3 libxrender1 \
      libxss1 \
      libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libfontconfig1 fonts-noto-color-emoji; \
    (apt-get install -y --no-install-recommends fonts-liberation) \
      || apt-get install -y --no-install-recommends fonts-liberation2; \
    apt-get install -y --no-install-recommends libicu-dev; \
    ln -sf /usr/bin/python3 /usr/local/bin/python; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip && pip install -r requirements.txt

# Cài browsers ở build-time
RUN python3 -m playwright install chromium firefox webkit \
 && mkdir -p /ms-playwright && chmod -R a+rX /ms-playwright

# User thường
ARG UID=10001
ARG GID=10001
RUN groupadd -g ${GID} app && useradd -m -u ${UID} -g ${GID} app \
 && mkdir -p /home/app/.cache /home/app/.config /tmp/xdg \
 && chown -R ${UID}:${GID} /home/app /tmp/xdg

USER ${UID}:${GID}
ENV HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    XDG_CONFIG_HOME=/home/app/.config \
    XDG_RUNTIME_DIR=/tmp/xdg \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# Copy mã nguồn
COPY --chown=${UID}:${GID} . /app

# Mặc định chỉ chạy Chromium (nhanh/ổn định). Thêm firefox/webkit ở workflow nếu cần.
CMD ["pytest","-vv","tests","--browser=chromium","--screenshot=only-on-failure","--video=off","--tracing=retain-on-failure"]
