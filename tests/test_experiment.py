"""論文實驗：題庫建置、受試者編號分組、計分。用假的歷史資料，不需要網路。"""

import json
import random
import shutil
from pathlib import Path

import pytest

import build_experiment_items as bei
import make_assignments
import build_site

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "knowledge" / "experiment"
INDUSTRIES = ["24", "25", "28", "17", "02", "15", "10", "03"]


def fake_panel(n_stocks=160, seed=1):
    """2022-07～2025-03 的月收盤、決策月月均價、本益比等，隨機漫步產生"""
    rnd = random.Random(seed)
    months = [bei.add_months("2022-07", k) for k in range(33)]
    month_ends = {k: f"{k[:4]}{k[5:]}28" for k in months}
    decision = [month_ends[k] for k in months[12:30]]
    stocks = {}
    for j in range(n_stocks + 1):
        code = "0050" if j == n_stocks else f"{1101 + j}"
        p, close, avg, tv, bw = 50 + rnd.random() * 100, {}, {}, {}, {}
        drift = rnd.gauss(0, 0.02)
        for k in months:
            p *= 1 + drift + rnd.gauss(0, 0.08)
            day = month_ends[k]
            close[day] = round(p, 2)
            if day in decision:
                avg[k] = round(p * (1 + rnd.gauss(0, 0.03)), 2)
                tv[day] = round(rnd.uniform(0.5, 30), 2)
                bw[day] = [round(rnd.uniform(5, 40), 2) if rnd.random() > 0.1 else None, round(rnd.uniform(0, 8), 2),
                           round(rnd.uniform(0.6, 5), 2)]
        stocks[code] = {"n": f"公司{code}", "i": "ETF" if code == "0050" else INDUSTRIES[j % len(INDUSTRIES)],
                        "close": close, "avg": avg, "tv": tv, "bw": bw}
    events = {"1101": [["20230715", 0.97]], "0050": [["20240120", 0.98]]}
    return {"decision_dates": decision, "month_ends": month_ends, "stocks": stocks, "events": events}


@pytest.fixture()
def exp(tmp_path):
    for name in ("config.json", "macro_2023_2024.csv"):
        shutil.copy2(EXP / name, tmp_path / name)
    (tmp_path / "panel.json").write_text(json.dumps(fake_panel()), encoding="utf-8")
    # 留一個月 PMI 空白，題庫維持草稿、可以重建
    macro = tmp_path / "macro_2023_2024.csv"
    lines = macro.read_text(encoding="utf-8").splitlines()
    lines[-1] = lines[-1].rsplit(",", 1)[0] + ","
    macro.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def test_items_are_deterministic_and_stratified(exp):
    items, key = bei.build(exp)
    first = (exp / "items.v1.json").read_bytes()
    bei.build(exp)  # 草稿可以重建，而且結果完全一樣
    assert (exp / "items.v1.json").read_bytes() == first
    q = json.loads((exp / "config.json").read_text())["items"]["quota"]
    formal = [key["items"][it["id"]] for it in items["items"]]
    assert len(formal) == sum(q.values())
    assert sum(not r["ai_correct"] for r in formal) == q["wrong_buy"] + q["wrong_no"]
    assert sum(r["truth"] == "buy" for r in formal) == q["correct_buy"] + q["wrong_buy"]
    assert len({r["date"] for r in formal}) == len(formal) and len({r["code"] for r in formal}) == len(formal)
    for r in formal:
        assert abs(r["excess"]) >= 0.02 and (r["excess"] > 0) == (r["truth"] == "buy")


def test_public_items_hide_identity_and_answers(exp):
    items, key = bei.build(exp)
    text = json.dumps(items["items"], ensure_ascii=False)
    for qid, r in key["items"].items():
        assert r["name"] not in text and r["date"] not in text
    assert all("truth" not in it for it in items["items"]) and all("truth" in it for it in items["practice"])
    assert all(it["m"][0] == 100 for it in items["items"])  # 以 12 個月前為 100


def test_recommendation_is_equal_weight_consensus(exp):
    items, _ = bei.build(exp)
    for it in items["items"]:
        s = [it["advisors"][a["key"]]["s"] for a in items["advisors"]]
        assert it["rec"] == ("buy" if sum(s) / len(s) >= 0.5 else "no")


def test_macro_uses_previous_month_and_pmi_gap_marks_draft(exp):
    panel = json.loads((exp / "panel.json").read_text())
    macro = bei.load_macro(exp / "macro_2023_2024.csv")
    days, _ = bei.candidates(panel, json.loads((exp / "config.json").read_text())["items"], macro)
    assert days[0]["light"] == macro["2023-06"]["light"]  # 2023-07 決策日只看得到 6 月燈號
    assert bei.rate_dir("20230728") == 1 and bei.rate_dir("20250430") == 0
    items, _ = bei.build(exp)
    assert items["draft"] is True
    shutil.copy2(EXP / "macro_2023_2024.csv", exp / "macro_2023_2024.csv")  # 真實資料 PMI 已補齊
    items, _ = bei.build(exp)
    assert items["draft"] is False


def test_no_look_ahead_in_engine_inputs(exp):
    panel = json.loads((exp / "panel.json").read_text())
    days, _ = bei.candidates(panel, json.loads((exp / "config.json").read_text())["items"], bei.load_macro(exp / "macro_2023_2024.csv"))
    st = next(s for s in days[0]["stocks"] if s["c"] not in panel["events"])
    raw = panel["stocks"][st["c"]]["close"]
    hist = sorted(d for d in raw if d < days[0]["date"])[-12:]
    assert [round(v, 2) for v in st["m"]] == [round(raw[d] / raw[hist[0]] * 100, 2) for d in hist]


def test_final_bank_is_not_overwritten(exp):
    bei.build(exp)
    path = exp / "items.v1.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "draft": False}), encoding="utf-8")
    with pytest.raises(SystemExit):
        bei.build(exp)


def test_assignment_codes_are_block_balanced():
    rows = make_assignments.generate(40, seed=7)
    assert len({p for p, _ in rows}) == 40
    for start in range(0, 40, 8):
        block = [c for _, c in rows[start:start + 8]]
        assert sorted(block) == [0, 0, 1, 1, 2, 2, 3, 3]
    assert all(make_assignments.condition_of(p) == c for p, c in rows)


def test_study_page_builds_without_answers():
    out, _ = build_site.pages()
    html = out["study.html"]
    assert "/*ITEMS*/" not in html and "/*STUDY*/" not in html
    if (EXP / "key.v1.json").exists():
        key = json.loads((EXP / "key.v1.json").read_text(encoding="utf-8"))
        for qid, r in key["items"].items():
            if not qid.startswith("練習"):
                assert r["name"] not in html
    assert "noindex" in build_site.head("study.html", "<style></style>")
    assert "study.html" not in build_site.sitemap([n for n in out if n not in build_site.UNLISTED], {})


def test_scoring_metrics(exp):
    import sys
    sys.path.insert(0, str(ROOT / "analysis"))
    import score_study
    _, key = bei.build(exp)
    surveys = json.loads((EXP / "surveys.zh.json").read_text(encoding="utf-8"))
    formal = {q: r for q, r in key["items"].items() if not q.startswith("練習")}
    # 受試者一開始全部答錯，看到理專後一律照理專
    flip = {"buy": "no", "no": "buy"}
    trials = [{"item_id": q, "order": i + 1, "d1": flip[r["truth"]], "c1": 60, "d2": r["rec"], "c2": 100}
              for i, (q, r) in enumerate(formal.items())]
    s = {"pid": "T1", "cond": 1, "trials": trials, "pre": {"att1": "藍色"}, "post": {"att2": 1, "mc1": "只有六位理專的共識結論", "mc2": "不能"}}
    rows, p = score_study.score(s, key, surveys)
    assert p["rair"] == 1 and p["over_reliance"] == 1 and p["under_reliance"] == 0
    assert p["acc_initial"] == 0 and p["acc_final"] == round(sum(r["ai_correct"] for r in formal.values()) / len(formal), 4)
    assert p["manip_ok"] == 1 and p["attention_ok"] == 1
    wrong = sum(not r["ai_correct"] for r in formal.values())
    assert p["brier"] == round(wrong / len(formal), 4)  # 信心 100%：答錯的題目每題 1 分


def test_latest_reads_datapipe_array(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "analysis"))
    import score_study
    (tmp_path / "A_pre.json").write_text(json.dumps([{"trial_type": "advisor-study", "pid": "A", "trials": []}]), encoding="utf-8")
    (tmp_path / "B.json").write_text(json.dumps({"pid": "B", "trials": [{}]}), encoding="utf-8")
    (tmp_path / "TEST04_pre.json").write_text(json.dumps([{"trial_type": "advisor-study", "pid": "TEST04", "trials": []}]), encoding="utf-8")
    got = {s["pid"] for s in score_study.latest(tmp_path)}
    assert got == {"A", "B"}
