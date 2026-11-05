"""理專憲章「不可變動的核心（實）」的機器閘門：PR 改到核心，就必須附上變更單編號（CR-nnn）。

憲章：資料來源與數字的計算方式、六位理專的權重與判斷條件、KYC 風險上限、免責與風險說明文字、
本憲章本身，任何修改都必須先修改需求書，經需求者核准並通過全部回歸測試後才能上線。
分級與柱子地圖見 docs/變更分級與柱子地圖.md；變更單總表見 docs/變更紀錄.md。

用法（CI 的 pull_request 事件）：PR_BODY="..." python scripts/core_guard.py <base-ref>
  - 比對 base 與目前工作目錄；改到下列 CORE 就檢查 PR 說明有沒有 CR-nnn，而且這張單要列在 docs/變更紀錄.md
  - 沒改到核心 → 通過（外層的畫面、文案、配色不需要變更單）
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CR = re.compile(r"CR-\d{3}")
LOG = "docs/變更紀錄.md"

# (名稱, 檔案或 glob, 片段起點, 片段終點)；起終點為 None 表示整個檔案。json 檔可用 "json:鍵" 只看某一段
CORE = [
    ("六位理專的規則與資料", "web/index.template.html", "// ---------- 台股資料", "const TABS="),
    ("理專互評條件", "web/index.template.html", "const REVIEWER=", "function health("),
    ("KYC 風險上限（首頁擋意見）", "web/index.template.html", "// 理專憲章第四條「守風險」", "function renderBlocked("),
    ("KYC 風險上限（模擬倉擋個股跟單與回測）", "web/sim.template.html", "// 理專憲章第四條「守風險」", "// 守風險：模擬倉結束"),
    ("KYC 風險上限（考場擋理專意見）", "web/lab.template.html", "// 理專憲章第四條「守風險」", "// 守風險：考場結束"),
    ("六位理專的背景與可用欄位", "knowledge/advisors.zh.json", None, None),
    ("KYC 風險屬性測驗與上限", "knowledge/insider.zh.json", "json:quiz", None),
    ("免責聲明", "scripts/build_site.py", "DISCLAIMER = (", "SITE_NAME ="),
    ("理專憲章", "web/charter.template.html", None, None),
    ("資料來源與數字計算", "scripts/fetch_*.py", None, None),
    ("資料品質與證交所比對", "scripts/validate_data.py", None, None),
    ("資料品質與證交所比對", "scripts/crosscheck_twse.py", None, None),
    ("機器閘門", "scripts/core_guard.py", None, None),
    ("每日動作紀錄與晨報", "scripts/action_log.mjs", None, None),
    ("每日動作紀錄與晨報（觀察清單）", "knowledge/action_log.zh.json", None, None),
    ("理專辦公室：日誌、互評對話與虛擬帳戶", "scripts/advisor_desk.mjs", None, None),
    ("理專辦公室：補記", "scripts/backfill_desk.mjs", None, None),
    ("機器閘門", "tests/test_charter.py", None, None),
    ("機器閘門", ".github/workflows/*.yml", None, None),
]


def part(text, start, end):
    if text is None or start is None:
        return text
    if start.startswith("json:"):
        try:
            return json.dumps(json.loads(text).get(start[5:]), ensure_ascii=False, sort_keys=True)
        except ValueError:
            return text
    i = text.find(start)
    if i < 0:
        return None
    j = text.find(end, i) if end else -1
    return text[i:j if j >= 0 else None]


def old_text(base, path):
    r = subprocess.run(["git", "show", f"{base}:{path}"], cwd=ROOT, capture_output=True)
    return r.stdout.decode("utf-8") if r.returncode == 0 else None


def new_text(path):
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.exists() else None


def paths(pattern, base):
    if "*" not in pattern:
        return [pattern]
    now = {str(p.relative_to(ROOT)) for p in ROOT.glob(pattern)}
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", base], cwd=ROOT, capture_output=True, text=True)
    was = {p for p in r.stdout.split() if Path(p).match(pattern)}
    return sorted(now | was)


def changed_core(base, read_old=old_text, read_new=new_text):
    hits = []
    for name, pattern, start, end in CORE:
        for path in paths(pattern, base):
            if part(read_old(base, path), start, end) != part(read_new(path), start, end):
                hits.append(f"{name}（{path}）")
    return list(dict.fromkeys(hits))


def check(hits, body, log_text):
    """回傳錯誤訊息清單；空清單表示通過"""
    if not hits:
        return []
    ids = sorted(set(CR.findall(body or "")))
    if not ids:
        return [f"這個 PR 改到憲章的核心（實）：{'、'.join(hits)}。請先由需求者寫變更單，並在 PR 說明寫上 CR 編號（例如 CR-002）。"]
    missing = [i for i in ids if i not in (log_text or "")]
    if missing:
        return [f"PR 說明的 {'、'.join(missing)} 沒有列在 {LOG}，請先把變更單登錄到變更紀錄。"]
    return []


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    hits = changed_core(base)
    errs = check(hits, os.environ.get("PR_BODY", ""), new_text(LOG))
    for h in hits:
        print(f"core  {h}")
    if errs:
        for e in errs:
            print(f"::error::{e}")
        sys.exit(1)
    print("ok  沒有改到核心" if not hits else f"ok  改到核心，已附變更單 {'、'.join(sorted(set(CR.findall(os.environ.get('PR_BODY', '')))))}")


if __name__ == "__main__":
    main()
