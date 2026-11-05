import json

import fetch_rates as fr

# 2026-11-05 央行 Data/GetJsonFromArray 實際回應的格式（節錄）
RESP = {"headerSet": {"Table1": [{"data": "銀行名稱"}, {"data": "利率項目"}, {"data": "存期"}, {"data": "額度"},
                                 {"data": "固定利率(%)"}, {"data": "機動利率(%)"}]},
        "data": [["004臺　銀", "活期存款", "--", "一般", "--", "0.705"],
                 ["004臺　銀", "活期儲蓄存款　　　　　　　　　", "--", "一般", "--", "0.825"],
                 ["004臺　銀", "薪資轉帳活期儲蓄存款　　　　　", "--", "一般", "--", "0.885"],
                 ["004臺　銀", "定期存款", "1月", "一般", "1.225", "1.225"],
                 ["004臺　銀", "定期存款", "1月", "5佰萬", "0.710", "0.710"],
                 ["004臺　銀", "定期存款", "2月", "一般", "1.225", "1.225"],
                 ["004臺　銀", "定期存款", "1年", "一般", "1.700", "1.690"],
                 ["004臺　銀", "定期儲蓄存款", "3年", "一般", "1.785", "1.785"],
                 ["824連線銀", "定期存款", "6月", "一般", "1.485", "1.480"],
                 ["999某某銀", "定期存款", "6月", "一般", "1.000", "1.000"]],
        "datatitle": "牌告利率"}


def test_parse_long_rows():
    got = fr.parse(RESP)
    bot = got["臺灣銀行"]
    assert bot["d"] == {"活期": 0.705, "活儲": 0.825, "薪轉": 0.885}
    assert bot["td"] == {"1": [1.225, 1.225], "12": [1.7, 1.69]}  # 2 個月不收、5 佰萬額度不收
    assert bot["ts"] == {"36": [1.785, 1.785]}
    assert got["LINE Bank"]["td"]["6"] == [1.485, 1.48]
    assert "999某某銀" not in json.dumps(got, ensure_ascii=False)


def test_term_labels():
    assert fr.term("1月") == "1" and fr.term("1年") == "12" and fr.term("3年") == "36" and fr.term("--") is None


def test_missing_columns_raises():
    try:
        fr.parse({"headerSet": {"Table1": [{"data": "銀行名稱"}]}, "data": []})
    except ValueError:
        return
    raise AssertionError("欄位對不上時應該報錯")
