"""文件庫的權限過濾與出處驗證閘門（CR-016；論文第三章 3-5-3，條件三）。

兩件事都由程式決定，不靠語言模型自己遵守：
1. 權限過濾 allowed_units()：依查詢者的角色（與分區）只留下他有權取得的段落；預設拒絕，
   段落的 roles 沒列到的角色一律排除。檢索要在這一步之後才做，無權的段落不會交給模型。
2. 出處驗證閘門 gate()：模型回答後檢查三件事，全部通過才放行，否則換成固定的拒答文字。
   (1) 回答至少附一個段落代號；(2) 所附代號都在這次檢索取回的段落裡；(3) 查詢者有權取得那些段落。
   閘門只檢查出處存在與權限，不判斷內容對不對。

用法（命令列）：
  python scripts/kb_gate.py --role external --retrieved INS-LAW-01,INS-LAW-03 --answer 回答.txt
  python scripts/kb_gate.py --role staff --partition tech --list   列出這個角色看得到的段落代號
研究者電腦上有 kb-private/catalog_full.json（含受限文件）時優先讀它，否則讀公開的 catalog.json。
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "knowledge" / "governance" / "catalog.json"
FULL = ROOT / "kb-private" / "catalog_full.json"
ROLES = json.loads((ROOT / "knowledge" / "governance" / "roles.json").read_text(encoding="utf-8"))
REFUSAL = ROLES["refusal"]
CITE = re.compile(r"\b[A-Z]{3}-[A-Z0-9]{2,3}-[A-Z0-9]{1,3}\b")
ROLE_IDS = {r["id"] for r in ROLES["roles"]}


def load_catalog(path=None):
    p = Path(path) if path else (FULL if FULL.exists() else PUBLIC)
    return {u["code"]: u for u in json.loads(p.read_text(encoding="utf-8"))["units"]}


def can_read(unit, role, partition=None):
    """預設拒絕：角色要列在 roles 裡；分區限定的段落，業務分區人員只能讀自己分區的（管理者不受限）"""
    if role not in ROLE_IDS or role not in unit.get("roles", []):
        return False
    if unit.get("partition") and role != "admin":
        return partition == unit["partition"]
    return True


def allowed_units(catalog, role, partition=None):
    return {c: u for c, u in catalog.items() if can_read(u, role, partition)}


def cited(answer):
    return list(dict.fromkeys(CITE.findall(answer or "")))


def gate(answer, retrieved, role, catalog, partition=None):
    """回傳 {"ok": bool, "reasons": [...], "cited": [...], "final": 送給使用者的文字}"""
    codes = cited(answer)
    reasons = []
    if not codes:
        reasons.append("回答沒有附任何段落代號")
    missing = [c for c in codes if c not in set(retrieved)]
    if missing:
        reasons.append("所附代號不在這次檢索取回的段落中：" + "、".join(missing))
    denied = [c for c in codes if c not in catalog or not can_read(catalog[c], role, partition)]
    if denied:
        reasons.append("查詢者無權取得（或文件庫中沒有）：" + "、".join(denied))
    ok = not reasons
    return {"ok": ok, "reasons": reasons, "cited": codes, "final": answer if ok else REFUSAL}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--role", required=True, choices=sorted(ROLE_IDS))
    ap.add_argument("--partition")
    ap.add_argument("--catalog")
    ap.add_argument("--retrieved", default="")
    ap.add_argument("--answer")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    cat = load_catalog(a.catalog)
    if a.list:
        print("\n".join(allowed_units(cat, a.role, a.partition)))
        return
    text = Path(a.answer).read_text(encoding="utf-8") if a.answer else sys.stdin.read()
    r = gate(text, [c for c in a.retrieved.split(",") if c], a.role, cat, a.partition)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["ok"] else 2)


if __name__ == "__main__":
    main()
