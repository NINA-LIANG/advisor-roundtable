"""CR-016 文件庫：代號、目錄、權限過濾、出處驗證閘門、題庫檢查與實驗文件庫匯出"""
import json
import subprocess
import sys
from pathlib import Path

import build_catalog
import kb_gate
import validate_qbank
import csv

ROOT = Path(__file__).resolve().parent.parent


def cat():
    return {u["code"]: u for u in build_catalog.catalog()["units"]}


def test_catalog_is_valid_and_committed():
    c = build_catalog.catalog()
    assert build_catalog.check(c["units"]) == []
    committed = json.loads((ROOT / "knowledge" / "governance" / "catalog.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(c, ensure_ascii=False)), "請執行 python scripts/build_catalog.py 後一起提交"


def test_three_layers_and_internal_docs():
    c = cat()
    layers = {u["layer"] for u in c.values()}
    assert layers == {"1", "2", "3"}
    # 表 3-4：變更單、變更分級、憲章舊版為內部限定；憲章現行版公開
    assert c["GOV-CR-015"]["sensitivity"] == "內部限定" and c["GOV-LVL-E"]["sensitivity"] == "內部限定"
    assert c["CHT-V10-01"]["status"] == "已被取代" and c["CHT-V10-01"]["sensitivity"] == "內部限定"
    assert c["CHT-V11-01"]["status"] == "現行" and c["CHT-V11-01"]["sensitivity"] == "公開"
    assert all(u["sensitivity"] == "公開" for u in c.values() if u["layer"] in ("2", "3"))


def test_every_knowledge_item_has_code():
    for name, n in [("insider.zh.json", 44), ("basics.zh.json", 77), ("concepts.zh.json", 18), ("bookshelf.zh.json", 18)]:
        text = (ROOT / "knowledge" / name).read_text(encoding="utf-8")
        assert text.count('"code"') == n, name


def test_codes_did_not_change_content():
    """加代號只是加欄位：拿掉 code 之後，內文與加代號前完全相同（以匯出條件一的 strip_codes 為準）"""
    import export_corpus
    d = json.loads((ROOT / "knowledge" / "insider.zh.json").read_text(encoding="utf-8"))
    stripped = export_corpus.strip_codes(d)
    assert all("code" not in it for s in stripped["sections"] for it in s["items"])
    assert [it["t"] for s in stripped["sections"] for it in s["items"]] == [it["t"] for s in d["sections"] for it in s["items"]]


def test_permission_default_deny():
    c = cat()
    pub, internal = c["INS-LAW-01"], c["GOV-CR-015"]
    assert kb_gate.can_read(pub, "external") and kb_gate.can_read(pub, "staff", "tech") and kb_gate.can_read(pub, "admin")
    assert not kb_gate.can_read(internal, "external")
    assert kb_gate.can_read(internal, "staff", "div") and kb_gate.can_read(internal, "admin")
    assert not kb_gate.can_read(pub, "guest")  # 沒定義的角色一律拒絕
    note = {"code": "RST-TEC-01", "roles": ["staff", "admin"], "partition": "tech"}
    assert kb_gate.can_read(note, "staff", "tech") and not kb_gate.can_read(note, "staff", "value")
    assert kb_gate.can_read(note, "admin") and not kb_gate.can_read(note, "external")
    audit = {"code": "RST-AUD-01", "roles": ["admin"]}
    assert not kb_gate.can_read(audit, "staff", "tech") and kb_gate.can_read(audit, "admin")
    assert "GOV-CR-015" not in kb_gate.allowed_units(c, "external")


def test_gate_three_checks():
    c = cat()
    ok = kb_gate.gate("依法要先瞭解客戶（INS-LAW-01）", ["INS-LAW-01", "INS-LAW-02"], "external", c)
    assert ok["ok"] and ok["final"].startswith("依法")
    no_cite = kb_gate.gate("依法要先瞭解客戶", ["INS-LAW-01"], "external", c)
    assert not no_cite["ok"] and no_cite["final"] == kb_gate.REFUSAL
    not_retrieved = kb_gate.gate("見 INS-LAW-03", ["INS-LAW-01"], "external", c)
    assert not not_retrieved["ok"] and "不在這次檢索" in not_retrieved["reasons"][0]
    denied = kb_gate.gate("見 GOV-CR-015", ["GOV-CR-015"], "external", c)
    assert not denied["ok"] and "無權" in denied["reasons"][0]
    fake = kb_gate.gate("見 INS-LAW-99", ["INS-LAW-99"], "admin", c)
    assert not fake["ok"]


def test_qbank_template_passes_and_catches_errors():
    c = kb_gate.load_catalog(ROOT / "knowledge" / "governance" / "catalog.json")
    with (ROOT / "research" / "題庫" / "題庫範本.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    err, _ = validate_qbank.check(rows, c)
    assert err == []
    bad = dict(rows[5], 應拒答="否", 標準答案要點="x")  # 外部使用者問變更單卻標成應回答
    err, _ = validate_qbank.check([bad], c)
    assert any("應拒答應為" in e for e in err)
    err, _ = validate_qbank.check([dict(rows[0], 正確出處代號="INS-LAW-99")], c)
    assert any("不在文件庫" in e for e in err)


def test_export_condition1_has_no_governance(tmp_path):
    out = tmp_path / "corpus"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export_corpus.py"), "--out", str(out)], check=True, capture_output=True)
    c1 = out / "condition1"
    assert not (c1 / "knowledge" / "governance").exists()
    assert all('"code"' not in p.read_text(encoding="utf-8") for p in c1.rglob("*.json"))
    units = [json.loads(l) for l in (out / "condition23" / "units.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(units) == build_catalog.catalog()["count"]
    assert units[0]["indexed_text"].startswith("[代號 ")
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert m["files"] and all(len(h) == 64 for h in m["files"].values())


def test_kb_page_built():
    import build_site
    out, _ = build_site.pages()
    html = out["kb.html"]
    assert "研究問題一" in html and "RQ1" not in html
    assert "非投資建議" in html
    assert 'href="kb.html"' in out["about.html"] or build_site.SITE_URL + "kb.html" in out["about.html"]
