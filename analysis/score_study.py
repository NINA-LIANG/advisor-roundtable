"""把 DataPipe 收到的作答檔合併成分析用的表格，並算出每位受試者的指標。

用法：python analysis/score_study.py 下載的資料夾 [輸出資料夾]
  資料夾：從 Google 雲端硬碟 My Drive/DataPipe 下載的 *.json（檔名「編號_階段.json」），或受試者手動下載的作答檔
輸出（預設 experiment-private/，已在 .gitignore，不會進公開 repo）：
  trials.csv        每位受試者每題一列（正式題）
  participants.csv  每人一列：組別、各項指標、排除旗標
指標定義見改版建議文件「指標怎麼算」：RAIR、RSR、過度依賴、依賴不足、正確率、Brier、過度自信、信任、金融素養。
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "knowledge" / "experiment"
PHASE = {"pre": 1, "task": 2, "final": 3}


def latest(folder):
    """每位受試者只留進度最多的一份；預覽模式的資料不收"""
    best = {}
    for f in sorted(Path(folder).glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"skip  {f.name}（不是 JSON）", file=sys.stderr)
            continue
        if not isinstance(s, dict) or "pid" not in s or s.get("preview"):
            continue
        rank = (len(s.get("trials", [])), bool(s.get("post")), PHASE.get(f.stem.rsplit("_", 1)[-1], 0))
        if s["pid"] not in best or rank > best[s["pid"]][0]:
            best[s["pid"]] = (rank, s)
    return [s for _, s in best.values()]


def ratio(a, b):
    return round(a / b, 4) if b else ""


def score(s, key, surveys):
    trials = [t for t in s.get("trials", []) if t["item_id"] in key["items"]]
    rows = []
    for t in trials:
        k = key["items"][t["item_id"]]
        y, a = k["truth"], t.get("shown_rec") or k["rec"]
        rows.append({"pid": s["pid"], "cond": s["cond"] + 1, "item_id": t["item_id"], "order": t["order"], "d1": t["d1"], "c1": t["c1"],
                     "ai_rec": a, "ai_correct": int(a == y), "sigma": k["sigma"], "d2": t["d2"], "c2": t["c2"], "truth": y,
                     "correct1": int(t["d1"] == y), "correct2": int(t["d2"] == y), "switched": int(t["d1"] != t["d2"]),
                     "agree_ai": int(t["d2"] == a), "t_pre": t.get("t_pre"), "t_post": t.get("t_post"),
                     "opened": len(t.get("opened", [])), "w_moves": t.get("w_moves", 0),
                     "w_final": json.dumps(t.get("w_final", ""), ensure_ascii=False) if t.get("w_final") else ""})
    n = len(rows)
    rair_den = [r for r in rows if not r["correct1"] and r["ai_correct"]]
    rsr_den = [r for r in rows if r["correct1"] and not r["ai_correct"]]
    ai_wrong = [r for r in rows if not r["ai_correct"]]
    ai_right = [r for r in rows if r["ai_correct"]]
    brier = sum((r["c2"] / 100 - r["correct2"]) ** 2 for r in rows) / n if n else ""
    pre, post = s.get("pre", {}), s.get("post", {})
    fl = [q for q in surveys["pre"] if q.get("block") == "finlit"]
    trust = [q for q in surveys["post"] if q.get("block") == "trust"]
    tv = [8 - post[q["id"]] if q.get("reverse") else post[q["id"]] for q in trust if isinstance(post.get(q["id"]), int)]
    mc = {q["id"]: q for q in surveys["post"] if q.get("block") == "manipulation"}
    p = {"pid": s["pid"], "cond": s["cond"] + 1, "assigned_by": s.get("assigned_by", ""), "n_trials": n,
         "complete": int(n == len([q for q in key["items"] if not q.startswith("練習")]) and bool(post)),
         "acc_initial": ratio(sum(r["correct1"] for r in rows), n), "acc_final": ratio(sum(r["correct2"] for r in rows), n),
         "rair": ratio(sum(r["d2"] == r["ai_rec"] for r in rair_den), len(rair_den)),
         "rsr": ratio(sum(r["d2"] == r["d1"] for r in rsr_den), len(rsr_den)),
         "over_reliance": ratio(sum(r["agree_ai"] for r in ai_wrong), len(ai_wrong)),
         "under_reliance": ratio(sum(1 - r["agree_ai"] for r in ai_right), len(ai_right)),
         "switch_rate": ratio(sum(r["switched"] for r in rows), n),
         "brier": round(brier, 4) if n else "",
         "overconfidence": round(sum(r["c2"] for r in rows) / n / 100 - sum(r["correct2"] for r in rows) / n, 4) if n else "",
         "trust_mean": round(sum(tv) / len(tv), 3) if tv else "",
         "finlit_pre": sum(pre.get(q["id"]) == q["answer"] for q in fl),
         "finlit_post": sum(post.get(q["id"] + "_post") == q["answer"] for q in fl) if post else "",
         "attention_ok": int(pre.get("att1") == "藍色" and post.get("att2") == 1) if post else "",
         "manip_ok": int(all(post.get(i) == q["answer_by_cond"][s["cond"]] for i, q in mc.items())) if post else "",
         "recognized": post.get("recog", ""), "invest_exp": pre.get("invest_exp", ""), "fin_background": pre.get("fin_background", ""),
         "seconds_total": round(sum((r["t_pre"] or 0) + (r["t_post"] or 0) for r in rows)),
         "app_ver": s.get("app_ver", ""), "items_sha": s.get("items_sha", "")}
    return rows, p


def write(path, rows):
    if not rows:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"ok  {path}（{len(rows)} 列）")


def main(folder, out=ROOT / "experiment-private"):
    key = json.loads((EXP / "key.v1.json").read_text(encoding="utf-8"))
    surveys = json.loads((EXP / "surveys.zh.json").read_text(encoding="utf-8"))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    trials, people = [], []
    for s in latest(folder):
        rows, p = score(s, key, surveys)
        trials += rows
        people.append(p)
    write(out / "trials.csv", trials)
    write(out / "participants.csv", people)
    return trials, people


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(*sys.argv[1:3])
