# Dockerfile — Ubuntu 22.04 + Playwright (Chromium/Firefox/WebKit)
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# APT: set mirror HTTPS + bật main/restricted/universe/multiverse + retry
RUN set -eux; \
    printf '%s\n' \
      "deb https://azure.archive.ubuntu.com/ubuntu jammy main restricted universe multiverse" \
      "deb https://azure.archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse" \
      "deb https://security.ubuntu.com/ubuntu jammy-security main restricted universe multiverse" \
      > /etc/apt/sources.list; \
    echo 'Acquire::Retries "5"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' >/etc/apt/apt.conf.d/80retry; \
    apt-get update; \
    # Base tools trước
    apt-get install -y --no-install-recommends \
      ca-certificates curl git bash dumb-init tzdata \
      python3 python3-pip python3-venv python-is-python3; \
    # System deps cho browsers (Chromium/Firefox/WebKit)
    apt-get install -y --no-install-recommends \
      libasound2 \
      libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
      libcups2 libdbus-1-3 libdrm2 libgbm1 \
      libglib2.0-0 libgtk-3-0 libnss3 libnspr4 \
      libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
      libxrandr2 libxkbcommon0 libxshmfence1 libxext6 libxfixes3 libxrender1 \
      libxss1; \
    # fonts-liberation có lúc là gói 'fonts-liberation2' -> fallback
    (apt-get install -y --no-install-recommends fonts-liberation) \
      || apt-get install -y --no-install-recommends fonts-liberation2; \
    # libicu tùy mirror, jammy là 70; thêm fallback dev nếu thiếu binary exact
    (apt-get install -y --no-install-recommends libicu70) \
      || apt-get install -y --no-install-recommends libicu-dev; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài deps Python trước để tận dụng cache
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Cài browsers (không dùng --with-deps vì đã cài system deps ở trên)
RUN python -m playwright install chromium firefox webkit \
 && mkdir -p /ms-playwright && chmod -R a+rX /ms-playwright

# Tạo user thường
ARG UID=10001
ARG GID=10001
RUN groupadd -g ${GID} app && useradd -m -u ${UID} -g ${GID} app \
 && mkdir -p /home/app/.cache /home/app/.config /tmp/xdg \
 && chown -R ${UID}:${GID} /home/app /tmp/xdg /ms-playwright

USER ${UID}:${GID}
ENV HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    XDG_CONFIG_HOME=/home/app/.config \
    XDG_RUNTIME_DIR=/tmp/xdg \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# Mã nguồn (CI/runner sẽ bind-mount, nhưng để local build vẫn chạy được)
COPY --chown=${UID}:${GID} . /app

ENTRYPOINT ["dumb-init","--"]
CMD ["pytest","-vv","tests","--browser","chromium","--browser","firefox","--browser","webkit","--screenshot=only-on-failure","--video=off","--tracing=retain-on-failure"]
