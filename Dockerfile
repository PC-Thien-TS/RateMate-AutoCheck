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

# APT: dùng HTTPS + bật main/restricted/universe/multiverse + retry
RUN set -eux; \
    printf '%s\n' \
      "deb https://azure.archive.ubuntu.com/ubuntu jammy main restricted universe multiverse" \
      "deb https://azure.archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse" \
      "deb https://security.ubuntu.com/ubuntu jammy-security main restricted universe multiverse" \
      > /etc/apt/sources.list; \
    echo 'Acquire::Retries "5"; Acquire::http::Timeout "30"; Acquire::https::Timeout "30";' >/etc/apt/apt.conf.d/80retry; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl git bash dumb-init tzdata \
      python3 python3-pip python3-venv python-is-python3; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài deps Python trước để tận dụng cache
COPY requirements.txt /app/requirements.txt

# Đảm bảo có playwright CLI (nếu requirements.txt chưa khai báo)
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 || true \
 && pip install --no-cache-dir "playwright>=1.48,<1.50"

# Cài system deps cho Playwright theo distro (ổn định hơn tự liệt kê từng gói)
RUN set -eux; \
    python -m playwright install-deps; \
    python -m playwright install chromium firefox webkit; \
    mkdir -p /ms-playwright && chmod -R a+rX /ms-playwright

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

# Mã nguồn (CI sẽ bind-mount; copy để local build vẫn chạy được)
COPY --chown=${UID}:${GID} . /app

ENTRYPOINT ["dumb-init","--"]
CMD ["pytest","-vv","tests",
     "--browser","chromium","--browser","firefox","--browser","webkit",
     "--screenshot=only-on-failure","--video=off","--tracing=retain-on-failure"]
