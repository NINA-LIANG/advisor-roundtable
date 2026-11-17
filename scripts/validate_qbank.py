"""檢查論文實驗題庫（CR-016；論文第三章第六節、附錄一）。

用法：python scripts/validate_qbank.py 題庫.csv
題庫本身（含標準答案）放研究者電腦的 kb-private/ 或 experiment-private/，事先登錄前不公開；
公開儲存庫只放 research/題庫/題庫範本.csv 的格式與範例。
檢查：欄位齊全、題型與角色合法、出處代號存在於文件庫、應拒答與權限一致、各題型題數（對照表 3-5 預定題數）。
"""
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_gate import ROLE_IDS, can_read, load_catalog  # noqa: E402

COLS = ["題號", "題型", "查詢角色", "分區", "題目", "標準答案要點", "正確出處代號", "應拒答", "備註"]
PLAN = {"單一文件事實題": 40, "跨文件整合題": 25, "版本與時效題": 15, "出處追問題": 15, "無解題": 15, "受限內容題": 40}
TODO = "【待填】"


def check(rows, cat):
    err, warn = [], []
    ids = Counter(r["題號"] for r in rows)
    err += [f"題號重複：{k}" for k, n in ids.items() if n > 1]
    for r in rows:
        q = r["題號"]
        if r["題型"] not in PLAN:
            err.append(f"{q} 題型不在表 3-5：{r['題型']}")
        if r["查詢角色"] not in ROLE_IDS:
            err.append(f"{q} 查詢角色不對：{r['查詢角色']}（要用 external／staff／admin）")
        if r["應拒答"] not in ("是", "否"):
            err.append(f"{q} 應拒答只能填 是 或 否")
        if not r["題目"].strip():
            err.append(f"{q} 沒有題目")
        codes = [c.strip() for c in r["正確出處代號"].split(";") if c.strip()]
        for c in codes:
            if c not in cat:
                err.append(f"{q} 出處代號不在文件庫：{c}")
        if r["題型"] == "無解題" and (codes or r["應拒答"] != "是"):
            err.append(f"{q} 無解題應拒答，且不填出處代號")
        if r["應拒答"] == "否":
            if not codes:
                err.append(f"{q} 應回答的題目要填正確出處代號")
            elif not any(can_read(cat[c], r["查詢角色"], r["分區"] or None) for c in codes if c in cat):
                err.append(f"{q} 查詢角色無權取得任何正確出處，應拒答應為「是」")
            if not r["標準答案要點"].strip() or TODO in r["標準答案要點"]:
                warn.append(f"{q} 標準答案要點還沒填")
        elif r["題型"] == "受限內容題" and codes and all(can_read(cat[c], r["查詢角色"], r["分區"] or None) for c in codes if c in cat):
            err.append(f"{q} 受限內容題的無權查詢，查詢角色卻有權取得出處")
    return err, warn


def main():
    path = Path(sys.argv[1])
    with path.open(encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        missing = [c for c in COLS if c not in (rd.fieldnames or [])]
        if missing:
            print("✗ 缺少欄位：" + "、".join(missing))
            sys.exit(1)
        rows = list(rd)
    err, warn = check(rows, load_catalog())
    for w in warn:
        print("⚠ " + w)
    for e in err:
        print("✗ " + e)
    n = Counter(r["題型"] for r in rows)
    print("題數：" + "、".join(f"{t} {n.get(t, 0)}/{p}" for t, p in PLAN.items()) + f"，合計 {len(rows)}/{sum(PLAN.values())}")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
