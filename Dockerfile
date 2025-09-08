# Dùng image Playwright đã kèm browsers tương thích (1.47.0)
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CI=1

WORKDIR /app

# Cài deps Python của dự án (nếu có),
# *KHÔNG* cài/chạm tới gói Playwright để tránh mismatch với image.
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    if [ -s requirements.txt ]; then \
      # Lọc bỏ dòng 'playwright' để không đè phiên bản có sẵn trong image, nhưng giữ lại 'pytest-playwright'
      grep -viE '^\s*playwright\b' requirements.txt > /tmp/req.filtered || true; \
      # Nếu file lọc rỗng thì bỏ qua, ngược lại thì cài
      if [ -s /tmp/req.filtered ]; then pip install -r /tmp/req.filtered; fi; \
    fi

# Copy source
COPY . /app

# Không đặt CMD cố định — workflow sẽ điều khiển lệnh pytest bên trong `docker run`
