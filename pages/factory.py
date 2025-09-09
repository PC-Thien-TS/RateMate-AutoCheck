# pages/factory.py
from .auth.login_page import LoginPage
from .auth.register_page import RegisterPage

class PageFactory:
    def __init__(self, page, site_cfg: dict):
        self.page = page
        self.cfg = site_cfg

    def login(self) -> LoginPage:
        return LoginPage(self.page, self.cfg["base_url"],
                         self.cfg.get("login_path", "/en/login"))

    def register(self) -> RegisterPage:
        return RegisterPage(self.page, self.cfg["base_url"],
                            self.cfg.get("register_path", "/en/login"))

__all__ = ["LoginPage", "RegisterPage", "PageFactory"]
    