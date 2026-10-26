"""理專輸出的合理性檢查：程式照規則跑完、單元測試也通過，結果仍可能不合常理（P09：汽車同業本益比中位數 341 倍）。
這裡不檢查規則細節，只檢查「什麼結果一定不對」：分數超出範圍、比較基準落在同業最小值與最大值之外、
規則參考價和現價差到不合理。"""

import json
import re
import subprocess
from pathlib import Path

import fetch_twse

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "scripts" / "advisor_engine.mjs"


def run_engine(stocks, light="綠", rate=0, pmi=50.5):
    inp = {"dates": [{"date": "20261024", "light": light, "rate": rate, "pmi": pmi, "stocks": stocks}]}
    out = subprocess.run(["node", str(ENGINE)], input=json.dumps(inp), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["dates"][0]["results"]


def stock(code, i, pe, p=100.0):
    return {"c": code, "n": code, "i": i, "p": p, "ma": p, "m": [p] * 12, "tv": 5, "pe": pe, "dy": 3, "pb": 1.5}


def basis(why):
    """從價值派理由取出比較用的中位數與檔數"""
    m = re.search(r"中位數 ([\d.]+) 倍", " ".join(why))
    return float(m.group(1)) if m else None


def test_scores_stay_in_range_on_current_data():
    stocks = json.loads((ROOT / "data" / "tw.json").read_text(encoding="utf-8"))["stocks"]
    res = run_engine(stocks)
    for code, r in res.items():
        for k in ("tech", "macro", "value", "mom", "quant", "div"):
            assert -2 <= r[k]["s"] <= 2, (code, k, r[k]["s"])


def test_value_basis_is_within_peer_range_on_current_data():
    stocks = json.loads((ROOT / "data" / "tw.json").read_text(encoding="utf-8"))["stocks"]
    res = run_engine(stocks)
    pes = [s["pe"] for s in stocks if s.get("pe") and s["pe"] > 0]
    for s in stocks:
        if not (s.get("pe") and s["pe"] > 0):
            continue
        med = basis(res[s["c"]]["value"]["why"])
        assert med is not None, s["c"]
        peers = [x["pe"] for x in stocks if x["i"] == s["i"] and x.get("pe") and x["pe"] > 0]
        lo, hi = (min(peers), max(peers)) if len(peers) >= 5 else (min(pes), max(pes))
        assert lo <= med <= hi, (s["c"], med, lo, hi)
        assert med < 150, f"{s['c']} 的比較基準 {med} 倍不合常理"


def test_two_stock_industry_falls_back_to_market_median():
    # 重現 P09：汽車類只有兩檔有本益比，其中一檔 341 倍
    stocks = [stock("2207", "12", 13.03, 530), stock("9999", "12", 341.25)]
    stocks += [stock(f"1{n:03d}", "24", 10 + n) for n in range(30)]
    r = run_engine(stocks)["2207"]["value"]
    med = basis(r["why"])
    assert med < 50 and "全市場" in " ".join(r["why"])
    m = re.search(r"參考價(?:為 <b>)? ?([\d.]+)", r["entry"])
    ref = float(m.group(1))
    assert 0.2 < ref / 530 < 5, r["entry"]


def test_peer_pe_uses_all_listed_stocks_and_averages_even_counts():
    bw = {"2207": {"PEratio": "13.03"}, "2201": {"PEratio": "20"}, "2330": {"PEratio": "27"},
          "1101": {"PEratio": "-"}, "0050": {"PEratio": "30"}}
    ind = {"2207": "12", "2201": "12", "2330": "24", "1101": "01"}
    ind_pe, mkt = fetch_twse.peer_pe(bw, ind)
    assert ind_pe["12"] == {"med": 16.52, "n": 2}
    assert "01" not in ind_pe and mkt == 20  # 虧損與 ETF 不算
