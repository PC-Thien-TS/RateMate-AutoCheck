# pages/factory.py
import os

SITE = (os.getenv("SITE") or "").strip().lower()

from .auth.login_page import LoginPage
from .register_page_site2 import RegisterPageSite2 as RegisterPage
