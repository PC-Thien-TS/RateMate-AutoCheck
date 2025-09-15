# pages/factory.py
from importlib import import_module
from typing import Any, Dict

from pages.auth.login_page import LoginPage as GenericLoginPage, LoginResult
from pages.auth.register_page import RegisterPage as GenericRegisterPage


class PageFactory:
    """Factory for lazily importing site specific pages."""

    def __init__(self, page, opts: Dict[str, Any]):
        self.page = page
        self.opts = opts or {}

    def _import_site_class(self, module_suffix: str, class_name: str):
        site = (self.opts.get("site") or "").strip().lower()
        if not site:
            return None
        module_name = f"pages.sites.{site}.{module_suffix}"
        try:
            module = import_module(module_name)
            return getattr(module, class_name)
        except Exception:
            return None

    def login(self):
        cls = self._import_site_class("auth_login", "LoginPage")
        base_url = self.opts.get("base_url", "")
        login_path = self.opts.get("login_path", "/login")
        if cls:
            return cls(self.page, base_url, login_path)
        return GenericLoginPage(self.page, base_url, login_path)

    def register(self):
        cls = self._import_site_class("auth_register", "RegisterPage")
        base_url = self.opts.get("base_url", "")
        register_path = self.opts.get("register_path", "/register")
        if cls:
            return cls(self.page, base_url, register_path)
        try:
            return GenericRegisterPage(self.page, base_url, register_path)
        except Exception:
            return None


# Re-export generic pages for convenience imports
LoginPage = GenericLoginPage
RegisterPage = GenericRegisterPage

__all__ = ["PageFactory", "LoginPage", "RegisterPage", "LoginResult"]
