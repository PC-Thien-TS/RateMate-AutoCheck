import os
import pytest
from dotenv import load_dotenv

# Tự load .env nếu có
load_dotenv(dotenv_path=os.getenv("DOTENV_PATH", ".env"), override=True)

def _pick_base_url() -> str:
    env = os.getenv("ENV", "prod").lower()
    if env == "staging":
        return os.getenv("BASE_URL_STAGING")
    return os.getenv("BASE_URL_PROD")

@pytest.fixture(scope="session")
def base_url():
    url = _pick_base_url()
    assert url, "BASE_URL_* chưa được cấu hình trong .env"
    return url.rstrip("/")

@pytest.fixture(scope="session")
def auth_paths():
    return {
        "login": os.getenv("LOGIN_PATH", "/en/login"),
        "register": os.getenv("REGISTER_PATH", "/en/register"),
    }

@pytest.fixture(scope="session")
def credentials():
    return {
        "email": os.getenv("LOGIN_EMAIL"),
        "password": os.getenv("LOGIN_PASSWORD"),
    }

# ---- PLAYWRIGHT FIXTURES ----
# Dùng option --browser (có sẵn của pytest-playwright): chromium | firefox | webkit
# KHÔNG tự add lại option --browser để tránh xung đột.

@pytest.fixture
def context_kwargs():
    return {
        "locale": "en-US",
        "permissions": [],
        "java_script_enabled": True,
        # headless: mặc định là True trên CI/container
    }

@pytest.fixture
def new_context(browser, context_kwargs):
    # 'browser' fixture do pytest-playwright cung cấp
    ctx = browser.new_context(**context_kwargs)
    yield ctx
    ctx.close()

@pytest.fixture
def new_page(new_context):
    page = new_context.new_page()
    yield page
    page.close()
