import json
import shutil
from pathlib import Path

from crosscheck_twse import compare
from validate_data import validate

ROOT = Path(__file__).resolve().parent.parent


def tw():
    return {"asof": "2026-11-03",
            "stocks": [{"c": "2330", "n": "台積電", "p": 2295.0, "pe": 26.6, "dy": 0.96, "pb": 9.25},
                       {"c": "9999", "n": "虧損股", "p": 10.0, "pe": None, "dy": 0.0, "pb": 1.2}],
            "etfs": [{"c": "0050", "n": "元大台灣50", "p": 60.1, "pe": None, "dy": 3.1, "pb": None}]}


def twse(**over):
    closes = {"2330": {"ClosingPrice": "2,295.00"}, "9999": {"ClosingPrice": "10.00"}, "0050": {"ClosingPrice": "60.10"}}
    bw = {"2330": {"PEratio": "26.60", "DividendYield": "0.96", "PBratio": "9.25"},
          "9999": {"PEratio": "-", "DividendYield": "0.00", "PBratio": "1.20"}}
    for k, v in over.items():
        code, field = k.split("_")
        (closes if field == "ClosingPrice" else bw)[code][field] = v
    return closes, bw


def test_identical_numbers_pass():
    n, bad = compare(tw(), *twse())
    assert n == 3 and bad == []


def test_any_price_difference_fails():
    n, bad = compare(tw(), *twse(**{"2330_ClosingPrice": "2,290.00"}))
    assert [(b["c"], b["field"], b["twse"]) for b in bad] == [("2330", "p", 2290.0)]


def test_ratio_rounding_is_tolerated_but_real_gap_is_not():
    assert compare(tw(), *twse(**{"2330_PEratio": "26.605"}))[1] == []
    bad = compare(tw(), *twse(**{"2330_PEratio": "341.30"}))[1]
    assert [(b["c"], b["field"]) for b in bad] == [("2330", "pe")]


def test_missing_ratio_on_one_side_fails():
    bad = compare(tw(), *twse(**{"9999_PEratio": "12.00"}))[1]
    assert [(b["c"], b["field"]) for b in bad] == [("9999", "pe")]


def test_stock_missing_from_twse_close_table_fails():
    closes, bw = twse()
    del closes["0050"]
    assert [b["c"] for b in compare(tw(), closes, bw)[1]] == ["0050"]


def _repo(tmp_path, cc):
    for d in ("data", "knowledge"):
        shutil.copytree(ROOT / d, tmp_path / d, ignore=shutil.ignore_patterns("raw", "status.json", "chunks"))
    asof = json.loads((tmp_path / "data" / "tw.json").read_text(encoding="utf-8"))["asof"]
    (tmp_path / "data" / "crosscheck.json").write_text(json.dumps({"asof": asof, **cc}, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_mismatch_on_current_day_blocks_publishing(tmp_path):
    repo = _repo(tmp_path, {"checked": 400, "mismatches": [
        {"c": "2207", "n": "和泰車", "field": "pe", "site": 341.3, "twse": 13.03, "why": "本益比差距超過 0.01"}]})
    errors, _, status = validate(repo)
    assert any("crosscheck.json" in e and "2207" in e for e in errors) and not status["ok"]


def test_clean_or_skipped_crosscheck_does_not_block(tmp_path):
    errors, _, status = validate(_repo(tmp_path, {"checked": 400, "mismatches": []}))
    assert not any("crosscheck" in e for e in errors) and "一致" in status["crosscheck"]
    errors, _, status = validate(_repo(tmp_path / "b", {"skipped": "抓不到證交所網站", "checked": 0, "mismatches": []}))
    assert not any("crosscheck" in e for e in errors) and "沒有比對" in status["crosscheck"]
