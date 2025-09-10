# pages/factory.py
from importlib import import_module
from .auth.login_page import LoginPage as GenericLoginPage
from .auth.register_page import RegisterPage

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

    def login(self) -> LoginPage:
        cls = self._login_cls()
        return cls(self.page, self.cfg["base_url"],
                   self.cfg.get("login_path", "/en/login"))

    def register(self) -> RegisterPage:
        return RegisterPage(self.page, self.cfg["base_url"],
                            self.cfg.get("register_path", "/en/login"))

__all__ = ["LoginPage", "RegisterPage", "PageFactory"]
    
