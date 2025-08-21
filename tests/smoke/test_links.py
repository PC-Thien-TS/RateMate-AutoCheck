import csv
import os
import pytest
import os

def _rows():
    p = "fixtures/data/links.csv"
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

@pytest.mark.smoke
@pytest.mark.parametrize("locale", os.getenv("LOCALES","en").split(","))
@pytest.mark.parametrize("row", _rows(), ids=lambda r: r["path"])
def test_open_links_ok(new_page, base_url, locale, row):
    path = row["path"].strip()
    # thay /en/ -> /{locale}/ nếu có; nếu không có /en/ vẫn dùng path gốc
    if "/en/" in path:
        path = path.replace("/en/", f"/{locale}/")
    url = f"{base_url}{path}"
    resp = new_page.goto(url, wait_until="domcontentloaded")
    assert resp and resp.ok, f"{url} not OK (status={getattr(resp,'status',None)})"
