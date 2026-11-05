"""回歸測試（黃金樣本）：固定一份輸入資料，把六位理專「當時」的判斷存起來；之後每次改程式都重算一次比對。

為什麼需要：需求者提一個新需求，AI 改了 A 功能，可能順手動到理專規則（B 功能）。單元測試只檢查寫到的情境，
這裡則檢查 320 檔個股 × 2 種總經情境 × 六位理專的分數與互評提醒，任何一個判斷變了都會被抓出來，並列出是哪幾檔、哪位理專、從幾分變幾分。

判斷改變有兩種情形：
  - 不該變（新需求跟理專規則無關）→ 這是回歸錯誤，請 AI 修正，不要更新樣本
  - 本來就要變（例如 CR 核准修改價值派條件）→ 執行 `python tests/test_golden_opinions.py --update` 更新樣本，
    PR 的檔案差異會顯示 tests/golden/opinions_expected.json 改了哪些判斷，需求者逐筆確認是否都在變更單範圍內

輸入資料 tests/golden/opinions_input.json 是 2026-11-05 的上市個股快照，固定不再更新（換資料就不是同一把尺）。
理由文字（why）不比對：文案調整屬外層，不影響判斷。ETF 不經過理專規則引擎，不在本測試範圍。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "scripts" / "advisor_engine.mjs"
GOLDEN = ROOT / "tests" / "golden"
KEYS = ("tech", "macro", "value", "mom", "quant", "div")
NAMES = {"tech": "技術派", "macro": "總經派", "value": "價值派", "mom": "動能派", "quant": "量化派", "div": "存股派"}
# 兩種總經情境：景氣綠燈＋央行不動＋PMI 擴張；藍燈＋升息＋PMI 收縮，讓總經派兩個方向都被測到
SCENARIOS = [
    {"date": "20261105", "light": "綠", "rate": 0, "pmi": 50.5},
    {"date": "20261106", "light": "藍", "rate": 1, "pmi": 47.0},
]


def compute():
    stocks = json.loads((GOLDEN / "opinions_input.json").read_text(encoding="utf-8"))["stocks"]
    inp = {"dates": [{**sc, "stocks": stocks} for sc in SCENARIOS]}
    out = subprocess.run(["node", str(ENGINE)], input=json.dumps(inp), capture_output=True, text=True, check=True)
    res = {}
    for sc, day in zip(SCENARIOS, json.loads(out.stdout)["dates"]):
        tag = f"{sc['light']}燈"
        for code, r in sorted(day["results"].items()):
            res[f"{tag} {code}"] = {k: r[k]["s"] for k in KEYS} | {"alerts": sorted(a["on"] for a in r["alerts"])}
    return res


def diff(old, new):
    lines = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a == b:
            continue
        if a is None or b is None:
            lines.append(f"{key}：{'新增' if a is None else '消失'}")
            continue
        for k in KEYS:
            if a[k] != b[k]:
                lines.append(f"{key} {NAMES[k]}：{a[k]} → {b[k]}")
        if a["alerts"] != b["alerts"]:
            lines.append(f"{key} 互評提醒：{a['alerts']} → {b['alerts']}")
    return lines


def test_advisor_opinions_unchanged():
    expected = json.loads((GOLDEN / "opinions_expected.json").read_text(encoding="utf-8"))
    changes = diff(expected, compute())
    assert not changes, (
        f"理專判斷有 {len(changes)} 處和黃金樣本不同（前 30 筆）：\n" + "\n".join(changes[:30])
        + "\n\n如果這次的變更單本來就要改這些判斷，執行 python tests/test_golden_opinions.py --update；否則就是回歸錯誤。"
    )


if __name__ == "__main__" and "--update" in sys.argv:
    path = GOLDEN / "opinions_expected.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    new = compute()
    changes = diff(old, new)
    # 一檔一行，PR 的檔案差異就能直接看出哪幾檔的判斷變了
    body = ",\n".join(f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(new.items()))
    path.write_text("{\n" + body + "\n}\n", encoding="utf-8")
    print(f"已更新黃金樣本，共 {len(changes)} 處判斷改變：")
    print("\n".join(changes[:200]))
