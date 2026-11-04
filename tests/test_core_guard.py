import core_guard
from core_guard import check, part


def test_part_extracts_region_and_json_key():
    text = "A\n// ---------- 台股資料\nrules\nconst TABS=[]"
    assert part(text, "// ---------- 台股資料", "const TABS=") == "// ---------- 台股資料\nrules\n"
    assert part('{"quiz":{"a":1},"other":2}', "json:quiz", None) == '{"a": 1}'
    assert part(None, "x", "y") is None


def test_core_change_requires_logged_cr():
    hits = ["免責聲明（scripts/build_site.py）"]
    assert check([], "", "") == []
    assert "CR 編號" in check(hits, "改了免責文字", "")[0]
    assert "沒有列在" in check(hits, "依 CR-005 修改", "| CR-002 |")[0]
    assert check(hits, "依 CR-002 修改", "| CR-002 | ...") == []


def test_changed_core_detects_only_core_regions(monkeypatch):
    monkeypatch.setattr(core_guard, "paths", lambda pattern, base: [pattern] if "*" not in pattern else [])
    old = {"web/index.template.html": "UI 1\n// ---------- 台股資料\nrule=1\nconst TABS=[]\nconst REVIEWER={}\nfunction health(){}"}
    ui_only = {"web/index.template.html": old["web/index.template.html"].replace("UI 1", "UI 2")}
    rule = {"web/index.template.html": old["web/index.template.html"].replace("rule=1", "rule=2")}
    read_old = lambda base, p: old.get(p)
    assert core_guard.changed_core("b", read_old, lambda p: ui_only.get(p)) == []
    assert core_guard.changed_core("b", read_old, lambda p: rule.get(p)) == ["六位理專的規則與資料（web/index.template.html）"]
