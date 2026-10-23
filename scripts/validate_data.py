"""發佈前的資料品質關卡：資料壞掉就擋下來，網站繼續顯示上一份好資料。

用法：python scripts/validate_data.py [--status data/status.json]
  - 有「錯誤」（格式壞、筆數太少、價格不合理、知識庫欄位缺漏）→ 結束碼 1，每日更新不會提交也不會發佈
  - 只有「警告」（資料太舊、某支抓取程式失敗而沿用舊檔）→ 照常發佈，另外開 Issue 通知
  - --status 會寫出各份資料的日期、筆數、狀態，build_site.py 用它產生「資料狀態」頁
  - 在 GitHub Actions 裡，環境變數 STEPS 帶入 ${{ toJSON(steps) }}，用來記錄每支抓取程式的成敗
"""

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPE = dt.timezone(dt.timedelta(hours=8))
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 每份資料：檔名、名稱、用在哪一頁、超過幾天算太舊、由哪一個 Actions 步驟（id）產生
DATASETS = [
    ("tw", "tw.json", "上市股票與 ETF 收盤", "理專圓桌、模擬倉、考場", 5, "twse"),
    ("universe", "universe.json", "上市櫃全部股票與 ETF", "台股全覽", 5, "universe"),
    ("dividends", "dividends.json", "除權息與殖利率", "除權息行事曆", 5, "dividends"),
    ("rates", "rates.json", "銀行牌告利率", "存款利率", 7, "rates"),
    ("etf_holdings", "etf_holdings.json", "ETF 持股明細", "台股全覽", 10, "holdings"),
    ("popular", "popular.json", "人氣小報（人工整理）", "人氣小報", 45, None),
]
ADVISORS = ("tech", "macro", "value", "mom", "quant", "div")
ADVISOR_FIELDS = {"career": list, "risk": list, "criteria": list, "fields": list, "db": list, "blind": str, "client": str}


def pos(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def check_tw(d):
    err = []
    stocks, etfs = d.get("stocks", []), d.get("etfs", [])
    if len(stocks) < 200:
        err.append(f"個股只有 {len(stocks)} 檔（平常約 320 檔）")
    if len(etfs) < 20:
        err.append(f"ETF 只有 {len(etfs)} 檔（平常約 80 檔）")
    if len(d.get("dates", [])) != 13:
        err.append("dates 應該有 13 個日期")
    for s in stocks + etfs:
        c = s.get("c", "?")
        if not pos(s.get("p")):
            err.append(f"{c} 收盤價不合理：{s.get('p')}")
        m = s.get("m") or []
        if len(m) != 12 or not all(pos(v) for v in m):
            err.append(f"{c} 月收盤不是 12 個正數")
        if not s.get("n"):
            err.append(f"{c} 沒有名稱")
    for s in stocks:
        if not re.fullmatch(r"\d{4}", str(s.get("c", ""))):
            err.append(f"個股代號格式不對：{s.get('c')}")
    return len(stocks) + len(etfs), err[:20]


def check_universe(d):
    err = []
    for k, need in (("stock", 1500), ("etf", 150)):
        rows = d.get(k, [])
        if len(rows) < need:
            err.append(f"{k} 只有 {len(rows)} 筆（至少要 {need}）")
        priced = sum(1 for r in rows if len(r) > 4 and pos(r[4]))
        if rows and priced / len(rows) < 0.9:
            err.append(f"{k} 有收盤價的只有 {priced}/{len(rows)}")
    return len(d.get("stock", [])) + len(d.get("etf", [])), err


def check_dividends(d):
    err = [f"缺少 {k}" for k in ("up", "past", "yld", "etf") if not isinstance(d.get(k), list)]
    if not err and len(d["yld"]) < 1000:
        err.append(f"殖利率只有 {len(d['yld'])} 檔（平常約 1700 檔）")
    return sum(len(d.get(k) or []) for k in ("up", "past", "yld")), err


def check_rates(d):
    banks = d.get("banks", [])
    err = [] if len(banks) >= 10 else [f"銀行只有 {len(banks)} 家"]
    err += [f"第 {i + 1} 家銀行沒有名稱" for i, b in enumerate(banks) if not b.get("n")]
    return len(banks), err


def check_holdings(d):
    n = len(d.get("etfs", {}))
    return n, [] if n >= 20 else [f"ETF 持股只有 {n} 檔"]


def check_popular(d):
    err = [] if d.get("dca_etf") and d.get("dca_stock") else ["定期定額排行是空的"]
    return len(d.get("dca_etf", [])), err


CHECKS = {"tw": check_tw, "universe": check_universe, "dividends": check_dividends, "rates": check_rates,
          "etf_holdings": check_holdings, "popular": check_popular}


def check_knowledge(root):
    """知識庫是人工編輯的，最容易打錯字；欄位缺了網頁會整塊空白"""
    err = []
    docs = {}
    for p in sorted((root / "knowledge").glob("*.json")):
        try:
            docs[p.name] = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as e:
            err.append(f"knowledge/{p.name} 不是合法 JSON：{e}")
    adv = docs.get("advisors.zh.json")
    if adv is not None:
        for k in ADVISORS:
            a = adv.get(k)
            if not isinstance(a, dict):
                err.append(f"advisors.zh.json 少了理專 {k}")
                continue
            for f, typ in ADVISOR_FIELDS.items():
                if not isinstance(a.get(f), typ) or not a.get(f):
                    err.append(f"advisors.zh.json 的 {k}.{f} 缺少或格式不對（應為{'清單' if typ is list else '文字'}）")
    basics = docs.get("basics.zh.json")
    if basics is not None:
        for i, t in enumerate(basics.get("terms", [])):
            if not all(t.get(x) for x in ("g", "k", "d")):
                err.append(f"basics.zh.json 第 {i + 1} 個名詞缺少 g／k／d")
    insider = docs.get("insider.zh.json")
    if insider is not None:
        for i, s in enumerate(insider.get("sections", [])):
            if not all(s.get(x) for x in ("id", "title", "items")):
                err.append(f"insider.zh.json 第 {i + 1} 個分區缺少 id／title／items")
    return err


def validate(root=ROOT, today=None, steps=None):
    """回傳 (錯誤清單, 警告清單, 狀態)"""
    today = today or dt.datetime.now(TPE).date()
    steps = steps or {}
    errors, warnings, rows = [], [], []
    for key, fname, name, page, max_age, step in DATASETS:
        row = {"key": key, "file": f"data/{fname}", "name": name, "page": page, "asof": "", "count": 0,
               "age": None, "state": "ok", "note": "", "step": steps.get(step, {}).get("outcome", "") if step else ""}
        try:
            d = json.loads((root / "data" / fname).read_text(encoding="utf-8"))
            asof = str(d.get("asof") or d.get("issue") or "")
            if not DATE.match(asof):
                raise ValueError(f"資料日期格式不對：{asof!r}")
            row["asof"] = asof
            row["count"], bad = CHECKS[key](d)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            bad = [str(e)]
        if bad:
            row["state"], row["note"] = "error", "；".join(bad[:3])
            errors += [f"{fname}：{b}" for b in bad]
        else:
            row["age"] = (today - dt.date.fromisoformat(row["asof"])).days
            notes = []
            if row["age"] > max_age:
                notes.append(f"已經 {row['age']} 天沒更新（超過 {max_age} 天；連假期間屬正常）")
            if row["step"] == "failure":
                notes.append("今天抓取失敗，沿用上一份資料")
            if notes:
                row["state"], row["note"] = "warn", "；".join(notes)
                warnings += [f"{fname}：{n}" for n in notes]
        rows.append(row)
    kb = check_knowledge(root)
    errors += kb
    status = {
        "checked": dt.datetime.now(TPE).strftime("%Y-%m-%d %H:%M"),
        "ok": not errors, "datasets": rows, "knowledge": kb or ["全部通過"],
        "errors": errors, "warnings": warnings,
        "steps": {k: v.get("outcome", "") for k, v in steps.items()},
        "run": (f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                if os.environ.get("GITHUB_RUN_ID") else ""),
    }
    return errors, warnings, status


def main():
    try:
        steps = json.loads(os.environ.get("STEPS") or "{}")
    except ValueError:
        steps = {}
    errors, warnings, status = validate(steps=steps)
    if "--status" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--status") + 1])
        out.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in status["datasets"]:
        mark = {"ok": "ok  ", "warn": "warn", "error": "FAIL"}[r["state"]]
        print(f"{mark} {r['file']:<24} {r['asof'] or '-':<10} {r['count']:>5} 筆  {r['note']}")
    for w in warnings:
        print(f"::warning::{w}")
    for e in errors:
        print(f"::error::{e}")
    if errors:
        sys.exit(f"資料品質檢查沒過（{len(errors)} 項錯誤），這次不發佈")
    print("資料品質檢查通過")


if __name__ == "__main__":
    main()
