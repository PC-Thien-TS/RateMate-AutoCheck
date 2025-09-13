Dưới đây là **README.md** mới (đầy đủ, dán đè file cũ):

---

## Reporting and Test Case Metadata (ASCII)

- HTML report now includes extra columns: Case ID, Title, Browser.
- JUnit XML includes `case_id`, `case_title`, and `browser` properties.
- Make/PowerShell targets emit timestamped HTML and JUnit into `report/`.

Annotate tests to enrich reports:

```
@pytest.mark.tc(id="RM-LOGIN-001", title="Login with valid credentials", area="Auth", severity="High")
def test_login_success(...):
    ...
```

Run examples:

```
# Linux/macOS/WSL
make run        # report/report-<ts>.html, report/junit-<ts>.xml

# Windows PowerShell
./make.ps1 run  # report/report-<ts>.html, report/junit-<ts>.xml
```

---

# RateMate AutoCheck (E2E)

Bộ kiểm thử end-to-end cho **RateMate Store** (hiện tập trung 1 web: `https://store.ratemate.top`) với hai nhóm tính năng chính **Đăng nhập** và **Đăng ký**.
Sử dụng **Pytest + Playwright** theo mô hình **Page Object Model (POM)**, chạy được cục bộ, Docker và GitHub Actions.

---

## 1) Công nghệ & cấu trúc

* **Python** + **Pytest**
* **Playwright** (Chromium là mặc định, có thể mở rộng WebKit/Firefox)
* **POM**: `pages/**` (login, register, …)
* **Fixtures/Config**: đọc **`sites.yaml`** (ưu tiên) và **`.env`** (secrets)
* **Báo cáo**: hỗ trợ Excel/HTML/JUnit (tuỳ chọn)
* **CI**: `.github/workflows/e2e.yml`

**Cây thư mục chính:**

```
RateMate-AutoCheck/
├─ .github/workflows/           # CI (e2e.yml)
├─ fixtures/data/               # dữ liệu test (links.csv, users.csv...)
├─ pages/                       # POM
│  └─ auth/
│     ├─ login_page.py
│     └─ register_page.py       # (đã gộp bản “site2” -> robust)
├─ tests/                       # testcases
│  ├─ auth/                     # login/register
│  ├─ i18n/                     # chuyển ngôn ngữ
│  └─ smoke/                    # kiểm tra route cơ bản
├─ report/                      # artifacts (excel/html/junit, screenshot, trace)
├─ sites.yaml                   # cấu hình site (khuyến nghị)
├─ conftest.py                  # load config/fixtures
├─ Dockerfile, Makefile, make.ps1
├─ requirements.txt, .env.example
└─ README.md
```

---

## 2) Yêu cầu hệ thống

* Python 3.10+ (nếu chạy trực tiếp)
* Docker (khuyến nghị để đồng nhất môi trường)
* Make (Linux/macOS/WSL), PowerShell script có sẵn cho Windows
* Trình duyệt Playwright (cài qua lệnh bên dưới)

---

## 3) Chuẩn bị nhanh

```bash
# 1) Cài thư viện
pip install -r requirements.txt

# 2) Cài browser cho Playwright (chạy Chromium là đủ)
playwright install --with-deps chromium

# 3) Tạo file .env từ mẫu (điền tài khoản test)
cp .env.example .env
# Mở .env và điền:
# E2E_EMAIL=...
# E2E_PASSWORD=...

# 4) (Tùy chọn) Build Docker image
make build
```

> **Ghi chú về config:**
> Dự án ưu tiên đọc cấu hình từ **`sites.yaml`** (1 site duy nhất `ratemate`), còn **`.env`** chỉ để chứa **E2E\_EMAIL/E2E\_PASSWORD**. Nếu không có `sites.yaml`, bộ test sẽ fallback sang biến môi trường trong `.env`.

---

## 4) Cấu hình

### 4.1 `sites.yaml` (khuyến nghị)

```yaml
default_site: ratemate

sites:
  ratemate:
    base_url: "https://store.ratemate.top"
    login_path: "/en/login"
    register_path: "/en/login"    # nếu có trang /en/register thì đổi lại
    locales: ["en", "vi"]
    routes:
      - "/en/login"
      - "/en/store"
      - "/en/product"
      - "/en/QR"
```

### 4.2 `.env.example` (secrets)

```
# Tài khoản test (bắt buộc điền khi chạy)
E2E_EMAIL=
E2E_PASSWORD=
```

---

## 5) Chạy test

### 5.1 Chạy trực tiếp bằng Pytest

```bash
# Full auth + smoke (Chromium)
pytest -vv tests/auth tests/smoke/test_routes.py --browser=chromium

# Chỉ auth
pytest -vv tests/auth --browser=chromium

# Chỉ smoke routes
pytest -vv tests/smoke/test_routes.py --browser=chromium
```

**Mẹo debug giao diện:**

```bash
pytest -vv tests/auth --browser=chromium --headed --slowmo=200
```

### 5.2 Dùng Makefile (Linux/macOS/WSL)

```bash
# Build image Docker
make build

# Chạy full suite (Chromium + WebKit trong target smoke/run như cấu hình)
make run
make smoke

# Xem các targets sẵn có
make help
```

### 5.3 Windows PowerShell

```powershell
# Build
.\make.ps1 build

# Full suite
.\make.ps1 run

# Smoke routes
.\make.ps1 smoke
```

---

## 6) Markers & lọc test

Trong `pytest.ini` đã đăng ký:

* `@pytest.mark.smoke` – kiểm tra nhanh (mở trang, element cơ bản)
* `@pytest.mark.auth` – nhóm test Đăng nhập/Đăng ký

**Ví dụ chạy theo marker:**

```bash
pytest -m smoke --browser=chromium
pytest -m auth  --browser=chromium
```

---

## 7) Báo cáo & artifacts (tuỳ chọn)

* **Excel** (yêu cầu `pytest-excel`):

  ```bash
  pytest -vv tests --browser=chromium --excelreport=report/run.xlsx
  ```
* **HTML**:

  ```bash
  pytest -vv tests --browser=chromium --html=report/report.html --self-contained-html
  ```
* **JUnit** (cho CI):

  ```bash
  pytest -vv tests --browser=chromium --junitxml=report/junit.xml
  ```

> Ảnh chụp màn hình, trace, video được cấu hình ở lệnh chạy/Makefile (mặc định **only-on-failure** + **tracing=retain-on-failure**).

---

## 8) Tùy chọn đa trình duyệt

Chromium là mặc định để nhanh và ổn định.
Có thể bật WebKit/Firefox trong lệnh chạy/Makefile/CI khi cần độ phủ:

```bash
pytest -vv tests --browser=chromium --browser=webkit --browser=firefox
```

---

## 9) CI/CD (GitHub Actions)

Workflow mẫu nằm tại: `.github/workflows/e2e.yml`.
Khuyến nghị:

* Job chính dùng **Chromium** (nhanh)
* Nightly job riêng cho **WebKit/Firefox** nếu cần

Bạn có thể bật “Require status check” cho workflow **E2E** trước khi merge vào `main`.

---

## 10) Troubleshooting

* **Thiếu browser Playwright**
  Chạy: `playwright install --with-deps chromium`
* **Không có `E2E_EMAIL/E2E_PASSWORD`**
  Điền trong `.env` (copy từ `.env.example`)
* **Timeout khi mở trang**
  Kiểm tra mạng, `base_url` trong `sites.yaml`, hoặc thêm `--headed --slowmo=200` để quan sát.
* **Lỗi selector**
  UI thay đổi → cập nhật selector trong POM (`pages/auth/*.py`) hoặc mapping trong `sites.yaml`.
* **CI artefacts không xuất hiện**
  Đảm bảo đã tạo thư mục `report/` và thêm step upload artifacts trong workflow.

---

## 11) Quy ước phát triển

* Một nguồn cấu hình: `sites.yaml` (POM đọc qua `conftest.py`)
* Không hard-code tài khoản vào repo → dùng `.env`
* Mỗi component UI (modal, toast, navbar…) cân nhắc tách vào `pages/components/`
* Test phải độc lập, không phụ thuộc thứ tự; tránh dùng state chia sẻ giữa test

---

## 12) Giấy phép

Nội bộ dự án RateMate (cập nhật theo chính sách team của bạn).

---
