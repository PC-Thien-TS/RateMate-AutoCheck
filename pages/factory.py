# pages/factory.py
from importlib import import_module
from .auth.login_page import LoginPage as GenericLoginPage
from .auth.register_page import RegisterPage as GenericRegisterPage

class PageFactory:
    def __init__(self, page, site_cfg: dict):
        self.page = page
        self.cfg = site_cfg
        self.site = (site_cfg.get("site") or "").strip().lower()

    def _login_cls(self):
        """Resolve site-specific LoginPage if available; fallback to generic."""
        if self.site:
            mod_name = f"pages.sites.{self.site}.auth_login"
            try:
                mod = import_module(mod_name)
                cls = getattr(mod, "LoginPage", None)
                if cls:
                    return cls
            except Exception:
                pass
        return GenericLoginPage

    def _register_cls(self):
        """Resolve site-specific RegisterPage if available; fallback to generic."""
        if self.site:
            mod_name = f"pages.sites.{self.site}.auth_register"
            try:
                mod = import_module(mod_name)
                cls = getattr(mod, "RegisterPage", None)
                if cls:
                    return cls
            except Exception:
                pass
        return GenericRegisterPage

    def login(self) -> GenericLoginPage:
        cls = self._login_cls()
        return cls(self.page, self.cfg["base_url"],
                   self.cfg.get("login_path", "/en/login"))

    def register(self) -> GenericRegisterPage:
        cls = self._register_cls()
        return cls(self.page, self.cfg["base_url"],
                   self.cfg.get("register_path", "/en/login"))

# Re-export generic pages for convenience imports
LoginPage = GenericLoginPage
RegisterPage = GenericRegisterPage

__all__ = ["PageFactory", "LoginPage", "RegisterPage"]
    
