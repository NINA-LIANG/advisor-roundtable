import json

import fetch_financials as ff
from validate_data import check_financials

# 欄位名稱照證交所開放資料原樣（一般業、金控、月營收各一筆）
CI = [{"年度": "115", "季別": "2", "公司代號": "2330", "公司名稱": "台積電", "營業收入": "1500000000.00",
       "營業毛利（毛損）淨額": "900000000.00", "營業利益（損失）": "700000000.00", "稅前淨利（淨損）": "720000000.00",
       "本期淨利（淨損）": "610000000.00", "淨利（淨損）歸屬於母公司業主": "600000000.00", "基本每股盈餘（元）": "23.15"}]
BS = [{"年度": "115", "季別": "2", "公司代號": "2330", "資產總計": "7000000000.00", "負債總計": "2100000000.00",
       "權益總計": "4900000000.00", "歸屬於母公司業主之權益合計": "4800000000.00", "流動資產": "3000000000.00",
       "流動負債": "1200000000.00", "每股參考淨值": "185.10"}]
FH = [{"年度": "115", "季別": "2", "公司代號": "2881", "淨收益": "120000000.00", "繼續營業單位稅前損益": "80000000.00",
       "本期稅後淨利（淨損）": "70000000.00", "基本每股盈餘（元）": "5.10"}]
FH_BS = [{"年度": "115", "季別": "2", "公司代號": "2881", "資產總額": "900000000.00", "歸屬於母公司業主之權益": "80000000.00"}]
OTC = [{"SecuritiesCompanyCode": "6488", "年度": "115", "季別": "2", "營業收入": "", "本期淨利（淨損）": "-"}]
REV = [{"資料年月": "11509", "公司代號": "2330", "營業收入-當月營收": "330000000", "營業收入-上月比較增減(%)": "-2.345",
        "營業收入-去年同月增減(%)": "31.4", "累計營業收入-當月累計營收": "2800000000", "累計營業收入-前期比較增減(%)": "36.0"}]


def parse():
    return ff.parse([("ci", "is", CI), ("bs", "bs", BS), ("fh", "is", FH), ("fhbs", "bs", FH_BS), ("otc", "is", OTC), ("rev", "rev", REV)])


def test_parse_merges_tables_and_converts_units():
    fin, mrev, q, m = parse()
    row = dict(zip(ff.COLS, fin["2330"]))
    assert row["rev"] == 15000 and row["np"] == 6000 and row["eps"] == 23.15  # 千元 → 億元，EPS 維持元
    assert row["assets"] == 70000 and row["bvps"] == 185.1
    assert q == (2026, 2) and m == "2026-09"
    assert mrev["2330"] == ["2026-09", 3300.0, -2.3, 31.4, 28000.0, 36.0]


def test_financial_industry_uses_its_own_column_names():
    fin, *_ = parse()
    row = dict(zip(ff.COLS, fin["2881"]))
    assert row["rev"] == 1200 and row["pre"] == 800 and row["net"] == 700 and row["gp"] is None
    assert row["assets"] == 9000 and row["eqp"] == 800


def test_otc_english_code_and_blank_values():
    fin, *_ = parse()
    assert set(fin["6488"]) == {None}


def test_raw_mode_writes_file(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    many = [dict(CI[0], 公司代號=str(1000 + i)) for i in range(900)]
    (raw / "t187ap06_L_ci.json").write_text(json.dumps(many, ensure_ascii=False), encoding="utf-8")
    (raw / "t187ap05_L.json").write_text(json.dumps(REV, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "financials.json"
    monkeypatch.setattr(ff, "OUT", out)
    monkeypatch.setattr("sys.argv", ["x", "--raw", str(raw)])
    ff.main()
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["quarter"] == "2026 Q2" and len(d["fin"]) == 900 and "t187ap07_L_ci" in d["missing"]
    assert check_financials(d) == (900, [])


def test_check_flags_too_few_companies():
    n, err = check_financials({"fin": {"2330": [None] * 14}, "cols": list(ff.COLS), "quarter": "2026 Q2"})
    assert n == 1 and err
