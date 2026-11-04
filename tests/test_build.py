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


def test_study_is_unlisted_and_paused_until_ethics_review():
    out, _ = build_site.pages()
    for name, html in out.items():
        if name != "study.html":
            assert 'href="study.html"' not in html, f"{name} 還有實驗頁入口"
    cfg = json.loads((build_site.EXP / "config.json").read_text(encoding="utf-8"))["study"]
    if cfg.get("paused"):
        assert "研究暫停中" in out["study.html"]


def test_charter_page_is_linked_and_lists_six_principles():
    out, _ = build_site.pages()
    html = out["charter.html"]
    for word in ("有據", "依規則", "不保證", "守風險", "透明", "可檢驗"):
        assert f"<b>{word}</b>" in html, word
    assert "守風險 ＞ 有據 ＞ 依規則 ＞ 不保證 ＞ 透明 ＞ 易讀" in html
    assert build_site.SITE_URL + "charter.html" in out["about.html"]
    assert "charter.html" in build_site.sitemap([n for n in out if n not in build_site.UNLISTED], {k: "" for k in out})


def test_corrections_page_lists_every_entry_with_source():
    out, _ = build_site.pages()
    data = json.loads((build_site.ROOT / "knowledge" / "corrections.zh.json").read_text(encoding="utf-8"))
    ids = [e["id"] for e in data["items"]]
    assert len(ids) == len(set(ids)), "勘誤編號重複"
    assert ids == sorted(ids, reverse=True), "最新的勘誤要放最前面"
    for e in data["items"]:
        assert all(e.get(k) for k in ("found", "fixed", "page", "article", "wrong", "cause", "fix", "ref")), e["id"]
        assert e["found"] <= e["fixed"], e["id"]
        assert e["ref"].startswith("https://github.com/NINA-LIANG/advisor-roundtable/"), e["id"]
        assert e["id"] in out["corrections.html"]
    assert 'href="corrections.html"' in out["charter.html"]


def test_report_page_shows_morning_report():
    out, _ = build_site.pages()
    assert "/*REPORT*/" not in out["report.html"] and "/*ACTIONLOG*/" not in out["report.html"]
    assert 'href="report.html"' in out["charter.html"]
    assert "report.html" in build_site.sitemap([n for n in out if n not in build_site.UNLISTED], {k: "" for k in out})
