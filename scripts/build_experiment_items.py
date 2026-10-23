"""從 panel.json 做出論文實驗的凍結題庫（不需要網路，結果完全由種子決定）。

用法：python scripts/build_experiment_items.py [--force]
輸入：knowledge/experiment/panel.json（fetch_experiment_panel.py）、macro_2023_2024.csv、config.json
輸出：
  knowledge/experiment/items.v1.json   實驗頁用的題目：遮蔽股名與日期、價格以 12 個月前為 100 重新標度；
                                       正式題不含正確答案，練習題附答案與結果
  knowledge/experiment/key.v1.json     每題的真實股票、日期、3 個月報酬與正確答案（分析與事後揭曉用）
  knowledge/experiment/manifest.json   三個檔案的 SHA-256，寫進預先註冊

做法（對應改版建議文件「歷史題目」一節）：
1. 每個決策日（2023-07～2024-12 每月最後交易日）用當天成交值超過 1 億元的上市普通股當候選。
2. 六位理專的判斷由 scripts/advisor_engine.mjs 計算，規則就是首頁那一份；只給決策日以前的資料。
3. 正確答案：未來 3 個月含息報酬勝過 0050 →「買」對，否則「不買」對；差距在 ±2% 內的題目太模糊，不收。
4. 理專建議：六人等權平均分數 ≥ 0.5（首頁的「分批布局」以上）→ 買，否則不買。
5. 依「理專對／錯 × 正確答案買／不買」分層抽題，每個日期、每檔股票最多出現一次。
正式版（draft=false）產生後就不再覆寫，除非加 --force；PMI 還沒補齊時是草稿，可以重建。
"""

import csv
import hashlib
import json
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "knowledge" / "experiment"
BENCH = "0050"
# 央行升息日；過去 12 個月內有升息就算「升息循環」（見 macro_README.md）
RATE_HIKES = ("20230323", "20240321")


def load_macro(path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["data_month"]] = {"light": r["light"], "pmi": float(r["pmi"]) if r["pmi"].strip() else None}
    return rows


def prev_month(key):
    y, m = int(key[:4]), int(key[5:])
    return f"{y - (m == 1)}-{12 if m == 1 else m - 1:02d}"


def add_months(key, k):
    y, m = divmod(int(key[:4]) * 12 + int(key[5:]) - 1 + k, 12)
    return f"{y}-{m + 1:02d}"


def rate_dir(day):
    year_ago = f"{int(day[:4]) - 1}{day[4:]}"
    return 1 if any(year_ago < h <= day for h in RATE_HIKES) else 0


def factor(events, day):
    """除權息還原係數：day 之後每一次除權息都把 day 的價格往下調"""
    f = 1.0
    for ex, k in events:
        if day < ex:
            f *= k
    return f


def adj(s, events, day):
    p = s["close"].get(day)
    return p * factor(events, day) if p else None


def candidates(panel, cfg, macro):
    """回傳 (送進理專引擎的每日資料, 每檔候選的附加資訊)"""
    me, days, extra = panel["month_ends"], [], {}
    bench, bev = panel["stocks"][BENCH], panel["events"].get(BENCH, [])
    for day in panel["decision_dates"]:
        key = f"{day[:4]}-{day[4:6]}"
        hist = [me[add_months(key, -k)] for k in range(12, 0, -1)]
        fwd = me[add_months(key, cfg["horizon_months"])]
        r_bench = adj(bench, bev, fwd) / adj(bench, bev, day) - 1
        known = macro[prev_month(key)]  # 決策日當下已公布的是上個月的燈號與 PMI
        rows = []
        for code, s in panel["stocks"].items():
            if code == BENCH or not s["i"] or s["tv"].get(day, 0) < cfg["min_tv_e8"]:
                continue
            ev = panel["events"].get(code, [])
            m = [adj(s, ev, d) for d in hist]
            p, p_fwd, avg = adj(s, ev, day), adj(s, ev, fwd), s["avg"].get(key)
            if None in m or not (p and p_fwd and avg):
                continue
            base = 100 / m[0]  # 以 12 個月前的收盤為 100，受試者看不出真實價位
            pe, dy, pb = s["bw"].get(day, [None, None, None])
            rows.append({"c": code, "n": code, "i": s["i"], "p": round(p * base, 2), "ma": round(avg * factor(ev, day) * base, 2),
                         "m": [round(v * base, 2) for v in m], "tv": s["tv"][day], "pe": pe, "dy": dy, "pb": pb})
            r = p_fwd / p - 1
            extra[(day, code)] = {"name": s["n"], "r_stock": r, "r_bench": r_bench, "excess": r - r_bench}
        days.append({"date": day, "light": known["light"], "rate": rate_dir(day),
                     **({"pmi": known["pmi"]} if known["pmi"] is not None else {}), "stocks": rows})
    return days, extra


def run_engine(days):
    out = subprocess.run(["node", str(ROOT / "scripts" / "advisor_engine.mjs")], input=json.dumps({"dates": days}),
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def pool(days, engine, extra, cfg):
    """每一題（日期 × 股票）的理專判斷、共識與正確答案"""
    keys = [a["key"] for a in engine["advisors"]]
    rows = []
    for day, res in zip(days, engine["dates"]):
        for st in day["stocks"]:
            e, R = extra[(day["date"], st["c"])], res["results"][st["c"]]
            if abs(e["excess"]) < cfg["ambiguous_band"]:
                continue
            scores = [R[k]["s"] for k in keys]
            avg = sum(scores) / len(scores)
            rec = "buy" if avg >= cfg["buy_threshold"] else "no"
            truth = "buy" if e["excess"] > 0 else "no"
            rows.append({"date": day["date"], "code": st["c"], "stock": st, "macro": {k: day.get(k) for k in ("light", "rate", "pmi")},
                         "advisors": {k: R[k] for k in keys}, "alerts": R["alerts"], "avg": avg, "sigma": statistics.pstdev(scores),
                         "rec": rec, "truth": truth, "ai_correct": rec == truth, **e})
    return rows


def stats(rows):
    def acc(rs):
        return round(sum(r["ai_correct"] for r in rs) / len(rs), 3) if rs else None
    med = statistics.median(r["sigma"] for r in rows)
    wrong = [0 if r["ai_correct"] else 1 for r in rows]
    sig = [r["sigma"] for r in rows]
    corr = statistics.correlation(sig, wrong) if len(set(wrong)) > 1 and len(set(sig)) > 1 else None
    return {"n": len(rows), "ai_accuracy": acc(rows), "truth_buy_share": round(sum(r["truth"] == "buy" for r in rows) / len(rows), 3),
            "rec_buy_share": round(sum(r["rec"] == "buy" for r in rows) / len(rows), 3),
            "sigma_median": round(med, 3), "ai_accuracy_sigma_high": acc([r for r in rows if r["sigma"] > med]),
            "ai_accuracy_sigma_low": acc([r for r in rows if r["sigma"] <= med]),
            "corr_sigma_ai_wrong": round(corr, 3) if corr is not None else None}


def select(rows, cfg):
    """依分層名額抽題；同一日期、同一檔股票最多一次（練習題另外抽，不和正式題重複股票）"""
    rnd = random.Random(cfg["seed"])
    strata = {}
    for r in rows:
        strata.setdefault((r["ai_correct"], r["truth"]), []).append(r)
    for v in strata.values():
        v.sort(key=lambda r: (r["date"], r["code"]))
        rnd.shuffle(v)
    used_d, used_c = set(), set()

    def take(quota, distinct_dates=True):
        picked = []
        for (ok, truth), n in sorted(quota, key=lambda q: len(strata.get(q[0], []))):
            got = 0
            for r in strata.get((ok, truth), []):
                if got == n:
                    break
                if r["code"] in used_c or (distinct_dates and r["date"] in used_d):
                    continue
                picked.append(r)
                used_c.add(r["code"])
                used_d.add(r["date"])
                got += 1
            if got < n:
                raise SystemExit(f"題庫不夠：AI {'對' if ok else '錯'}、答案{truth} 只抽到 {got}／{n} 題")
        return picked

    q = cfg["quota"]
    formal = take([((True, "buy"), q["correct_buy"]), ((True, "no"), q["correct_no"]),
                   ((False, "buy"), q["wrong_buy"]), ((False, "no"), q["wrong_no"])])
    practice = take([((True, "buy"), 1), ((False, "no"), 1)], distinct_dates=False)
    rnd.shuffle(formal)
    return formal, practice


def public(r, qid, with_answer):
    st = r["stock"]
    item = {"id": qid, "label": f"股票 {qid}", "industry": r["advisors"]["macro"]["metrics"]["產業"],
            "p": st["p"], "ma": st["ma"], "m": st["m"], "pe": st["pe"], "dy": st["dy"], "pb": st["pb"], "macro": r["macro"],
            "advisors": r["advisors"], "alerts": r["alerts"], "avg": round(r["avg"], 3), "sigma": round(r["sigma"], 3), "rec": r["rec"]}
    if with_answer:
        item.update(truth=r["truth"], r_stock=round(r["r_stock"], 4), r_bench=round(r["r_bench"], 4))
    return item


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(exp=EXP, force=False):
    cfg = json.loads((exp / "config.json").read_text(encoding="utf-8"))["items"]
    panel = json.loads((exp / "panel.json").read_text(encoding="utf-8"))
    macro = load_macro(exp / "macro_2023_2024.csv")
    items_path, key_path = exp / "items.v1.json", exp / "key.v1.json"
    if items_path.exists() and not force and not json.loads(items_path.read_text(encoding="utf-8"))["draft"]:
        raise SystemExit("items.v1.json 已經是正式版（draft=false），不覆寫；真的要重做請加 --force 並改版本號")
    days, extra = candidates(panel, cfg, macro)
    engine = run_engine(days)
    rows = pool(days, engine, extra, cfg)
    formal, practice = select(rows, cfg)
    draft = any(d.get("pmi") is None for d in days)
    ids = [chr(65 + k) for k in range(len(formal))]
    head = {"version": 1, "draft": draft, "engine_sha": engine["engine_sha"], "seed": cfg["seed"],
            "panel_sha": sha(exp / "panel.json"), "horizon_months": cfg["horizon_months"], "pool": stats(rows)}
    items = {**head, "advisors": engine["advisors"],
             "practice": [public(r, f"練習{k + 1}", True) for k, r in enumerate(practice)],
             "items": [public(r, q, False) for q, r in zip(ids, formal)]}
    key = {**head, "items": {q: {"code": r["code"], "name": r["name"], "date": r["date"], "truth": r["truth"], "rec": r["rec"],
                                 "ai_correct": r["ai_correct"], "sigma": round(r["sigma"], 3), "r_stock": round(r["r_stock"], 4),
                                 "r_bench": round(r["r_bench"], 4), "excess": round(r["excess"], 4)}
                             for q, r in [*zip(ids, formal), *((f"練習{k + 1}", r) for k, r in enumerate(practice))]}}
    items_path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    key_path.write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    (exp / "manifest.json").write_text(json.dumps({"items.v1.json": sha(items_path), "key.v1.json": sha(key_path),
                                                   "panel.json": head["panel_sha"], "engine_sha": head["engine_sha"]}, indent=1),
                                       encoding="utf-8")
    print(f"ok  {len(formal)} 題正式題＋{len(practice)} 題練習題，候選 {len(rows)} 題，AI 準確率 {head['pool']['ai_accuracy']}"
          f"{'（草稿：PMI 未補齊）' if draft else ''}")
    return items, key


if __name__ == "__main__":
    build(force="--force" in sys.argv)
