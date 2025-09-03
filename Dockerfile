# Dockerfile — chạy đủ Chromium/Firefox/WebKit, không cần MCR
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# --- APT bootstrap qua HTTP để cài ca-certificates trước (tránh lỗi TLS) ---
RUN set -eux; \
    printf '%s\n' \
      "deb http://archive.ubuntu.com/ubuntu jammy main restricted universe multiverse" \
      "deb http://archive.ubuntu.com/ubuntu jammy-updates main restricted universe multiverse" \
      "deb http://security.ubuntu.com/ubuntu jammy-security main restricted universe multiverse" \
      > /etc/apt/sources.list; \
    echo 'Acquire::Retries "5"; Acquire::http::Timeout "30";' >/etc/apt/apt.conf.d/80retry; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl git bash dumb-init tzdata \
      python3 python3-pip python3-venv python-is-python3; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*

# (Tuỳ chọn) Chuyển APT sang HTTPS sau khi đã có CA
RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu|https://security.ubuntu.com/ubuntu|g' /etc/apt/sources.list || true; \
    apt-get update || true

WORKDIR /app

# Cài deps Python trước để tận dụng cache layer
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

# Cài browsers + toàn bộ system deps cần thiết
# Dùng --with-deps để Playwright tự cài lib hệ thống qua APT
RUN python -m playwright install --with-deps chromium firefox webkit \
 && mkdir -p /ms-playwright && chmod -R a+rX /ms-playwright

# Tạo user thường để chạy an toàn
ARG UID=10001
ARG GID=10001
RUN groupadd -g ${GID} app && useradd -m -u ${UID} -g ${GID} app \
 && mkdir -p /home/app/.cache /home/app/.config /tmp/xdg \
 && chown -R ${UID}:${GID} /home/app /tmp/xdg /app

USER ${UID}:${GID}
ENV HOME=/home/app \
    XDG_CACHE_HOME=/home/app/.cache \
    XDG_CONFIG_HOME=/home/app/.config \
    XDG_RUNTIME_DIR=/tmp/xdg \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# Mã nguồn (khi chạy thực tế có thể bind-mount từ host)
COPY --chown=${UID}:${GID} . /app

ENTRYPOINT ["dumb-init","--"]
CMD ["pytest","-vv","tests","--browser","chromium","--browser","firefox","--browser","webkit","--screenshot=only-on-failure","--video=off","--tracing=retain-on-failure"]
