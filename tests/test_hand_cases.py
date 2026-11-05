"""需求者自算案例：預期值不是程式算的，而是需求者依規則文字在 Excel 裡自己算出來的
（thesis/site-changes/自算驗證練習_價值派三檔.xlsx，資料與黃金樣本同一份 2026-11-05 快照）。

和黃金樣本的差別：黃金樣本只能證明「和上次一樣」；這裡的預期值來自需求者，能證明「和需求者理解的規則一樣」。
新增案例時，每一筆都要附上手算過程（中位數、同業比），之後有人看到失敗訊息才知道錯在哪一步。
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "scripts" / "advisor_engine.mjs"

# (代號, 同業有本益比檔數, 採用的中位數, 同業比, 價值派分數, 規則參考價, 手算說明)
CASES = [
    ("2317", 18, 22.97, 0.689, 2, 272.97, "鴻海：15.82 ÷ 同業中位數 22.97 = 0.689，小於 0.7（邊界附近）→ +2"),
    ("2882", 18, 14.77, 0.886, 1, 101.10, "國泰金：13.09 ÷ 同業中位數 14.77 = 0.886，介於 0.7 與 0.9 → +1"),
    ("2207", 3, 20.82, 0.631, 2, 681.21, "和泰車：同業只有 3 檔（少於 5），改用全市場中位數 20.82；13.13 ÷ 20.82 = 0.631 → +2"),
]


@pytest.fixture(scope="module")
def results():
    stocks = json.loads((ROOT / "tests" / "golden" / "opinions_input.json").read_text(encoding="utf-8"))["stocks"]
    inp = {"dates": [{"date": "20261105", "light": "綠", "rate": 0, "pmi": 50.5, "stocks": stocks}]}
    out = subprocess.run(["node", str(ENGINE)], input=json.dumps(inp), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["dates"][0]["results"]


@pytest.mark.parametrize("code,n,med,rel,score,cheap,how", CASES, ids=[c[0] for c in CASES])
def test_value_advisor_matches_hand_calculation(results, code, n, med, rel, score, cheap, how):
    r = results[code]["value"]
    why = " ".join(r["why"])
    assert f"{med:.1f} 倍" in why, f"{how}；網站用的中位數不同：{why}"
    assert r["s"] == score, f"{how}；網站給 {r['s']} 分"
    # 網站顯示到小數一位
    assert f"規則參考價 {cheap:.1f}" in r["entry"] or f"規則參考價為 <b>{cheap:.1f}</b>" in r["entry"], \
        f"{how}；規則參考價應約為 {cheap:.1f}，網站寫：{r['entry']}"
