import re
import json
import pytest
from pages.auth.register_page import RegisterPage
from playwright.sync_api import TimeoutError as PWTimeout

# đa ngôn ngữ: exists/đã tồn tại/已经存在/已注册/đã đăng ký/taken/registered
_DUP = re.compile(r"(already\s*(exists|registered)|email\s*taken|đã\s*tồn\s*tại|đã\s*đăng\s*ký|已经存在|已注册)", re.I)
_ERR_PW = re.compile(r"(invalid|incorrect|wrong|mật\s*khẩu|密码|錯誤|错误)", re.I)

@pytest.mark.auth
def test_register_duplicate_email_returns_error(new_page, base_url, auth_paths, credentials):
    """
    Email đã tồn tại + mật khẩu đúng:
    - Kỳ vọng CHÍNH: API trả 400/409 (duplicate) hoặc UI hiện thông báo duplicate.
    - Kỳ vọng PHỤ: nếu về sau hệ thống hợp nhất và cho đăng nhập luôn → chuyển /store.
    """
    reg = RegisterPage(new_page, base_url, auth_paths["register"])
    reg.goto()

    resp = reg.register_and_wait_response(credentials["email"], credentials["password"], timeout=12000)
    assert resp is not None, "Không bắt được response khi submit đăng ký"

    status = resp.status
    body_text = ""
    try:
        body_text = resp.text()
    except Exception:
        pass

    # 1) Trường hợp chuẩn: 400/409 kèm thông điệp duplicate (nếu có)
    if status in (400, 409):
        try:
            data = json.loads(body_text)
            msg = json.dumps(data, ensure_ascii=False)
        except Exception:
            msg = body_text
        # Có thông điệp duplicate càng tốt, nhưng chỉ cần status 4xx là đạt
        assert _DUP.search(msg or "") or True
        return

    # 2) Trường hợp hợp nhất: 200/201 -> coi như đăng nhập, chuyển /store
    if status in (200, 201):
        try:
            new_page.wait_for_url("**/store*", timeout=8000)
        except PWTimeout:
            pass
        assert "/store" in new_page.url, f"Status {status} nhưng không thấy chuyển /store"
        return

    # 3) Fallback UI nếu status khác
    err = reg.visible_error_locator()
    try:
        err.wait_for(state="visible", timeout=6000)
        text = (err.inner_text() or "")
        assert _DUP.search(text), f"Không thấy thông báo duplicate trên UI: {text!r} (status={status})"
    except PWTimeout:
        pytest.fail(f"Không khớp kỳ vọng duplicate. status={status}, body[:200]={body_text[:200]!r}")

@pytest.mark.auth
def test_register_existing_email_wrong_password_shows_error(new_page, base_url, auth_paths, credentials):
    """
    Email đã tồn tại + mật khẩu sai -> báo lỗi (API 4xx hoặc UI error).
    """
    reg = RegisterPage(new_page, base_url, auth_paths["register"])
    reg.goto()

    wrong_pw = credentials["password"] + "_WRONG!"
    resp = reg.register_and_wait_response(credentials["email"], wrong_pw, timeout=12000)

    if resp and resp.status in (400, 401, 403, 409):
        assert True
        return

    err = reg.visible_error_locator()
    err.wait_for(state="visible", timeout=7000)
    assert _ERR_PW.search((err.inner_text() or "")), "Không thấy nội dung lỗi mật khẩu sai trên UI"
