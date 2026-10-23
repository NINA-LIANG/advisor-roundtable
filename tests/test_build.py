import gzip
import json
import re

import build_site
import run_report
from snapshot_history import snapshot


def test_every_page_builds_with_nav_and_main():
    out, asof = build_site.pages()
    assert set(out) == set(build_site.META)
    for name, html in out.items():
        assert '<main id="main"' in html, name
        if name == "study.html":  # 實驗頁刻意不放導覽列
            continue
        assert 'class="sitenav"' in html and 'class="sitefoot"' in html, name
        assert not re.search(r"/\*[A-Z]+\*/", html), f"{name} 還有沒替換的資料標記"


def test_status_page_embeds_status():
    out, _ = build_site.pages()
    html = out["status.html"]
    assert "/*STATUS*/" not in html and '"datasets"' in html


def test_snapshot_is_written_once(tmp_path):
    day, wrote = snapshot(tmp_path)
    assert wrote
    tw = tmp_path / day[:4] / day[5:7] / day / "tw.json.gz"
    assert json.loads(gzip.decompress(tw.read_bytes()))["asof"] == day
    assert json.loads((tmp_path / "index.json").read_text())["dates"] == [day]
    assert snapshot(tmp_path) == (day, False)


def test_run_report_lists_failed_steps():
    body = run_report.report({"twse": {"outcome": "failure"}, "rates": {"outcome": "success"}}, None, "https://run")
    assert "❌ failure" in body and "https://run" in body


def test_run_report_explains_pages_not_enabled():
    body = run_report.report({"validate": {"outcome": "success"}, "pages": {"outcome": "failure"}}, None, "")
    assert "Settings → Pages" in body
