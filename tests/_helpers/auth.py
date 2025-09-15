import re
import contextlib

LOGIN_URL_RE = re.compile(r"/(auth/login|log[-_]?in|sign[-_]?in)(\?|/|$)", re.IGNORECASE)

_ERR_SEL = (
    "[role='alert'], [role='status'], "
    ".ant-form-item-explain-error, .ant-message-error, "
    ".ant-message-notice .ant-message-custom-content, "
    ".ant-notification-notice-message, .ant-notification-notice-description, "
    ".MuiAlert-root, .Toastify__toast--error, "
    ".error, .error-message, .text-danger, .invalid-feedback, "
    ".el-message__content, .v-alert__content, .toast-message, .notification-message"
)

def has_error(page):
    loc = page.locator(_ERR_SEL).first
    with contextlib.suppress(Exception):
        if loc.is_visible(timeout=2000):
            with contextlib.suppress(Exception):
                txt = (loc.inner_text(timeout=500) or "").strip()
            return True, txt or ""
    return False, ""

def auth_state_ok(page) -> bool:
    with contextlib.suppress(Exception):
        for c in page.context.cookies():
            name = c.get("name", "") or ""
            val = c.get("value", "") or ""
            if re.search(r"(token|auth|jwt|access|refresh|session)", name, re.I) and len(val) >= 12:
                return True
    with contextlib.suppress(Exception):
        keys = page.evaluate("Object.keys(window.localStorage)")
        for k in keys:
            if re.search(r"(token|auth|jwt|access|refresh|session)", k, re.I):
                v = page.evaluate("localStorage.getItem(arguments[0])", k)
                if v and len(str(v)) >= 12:
                    return True
    with contextlib.suppress(Exception):
        keys = page.evaluate("Object.keys(window.sessionStorage)")
        for k in keys:
            if re.search(r"(token|auth|jwt|access|refresh|session)", k, re.I):
                v = page.evaluate("sessionStorage.getItem(arguments[0])", k)
                if v and len(str(v)) >= 12:
                    return True
    return False
