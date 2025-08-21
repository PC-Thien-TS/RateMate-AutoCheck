# Dockerfile — chạy đủ Chromium/Firefox/WebKit, không cần MCR
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CI=1

# Gói cơ bản + Python 3.10 + pip
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.10 python3-pip python3-venv python-is-python3 \
      curl ca-certificates git bash dumb-init tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài deps Python trước để tận dụng cache
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install -r requirements.txt

# Cài browsers + system deps (bao gồm libicu70) ở bước build (quyền root)
RUN python -m playwright install --with-deps chromium firefox webkit \
 && mkdir -p /ms-playwright && chmod -R a+rX /ms-playwright

# Tạo user thường
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

# Mã nguồn (khi chạy thực tế sẽ bị bind-mount từ host)
COPY --chown=${UID}:${GID} . /app

ENTRYPOINT ["dumb-init","--"]
CMD ["pytest","-vv","tests","--browser","chromium","--browser","firefox","--browser","webkit","--screenshot=only-on-failure","--video=off","--tracing=retain-on-failure"]
