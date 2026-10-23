"""把每日更新各步驟的成敗整理成 Issue 內文（Markdown），給 daily-update 的「通知」步驟用。

環境變數：STEPS（${{ toJSON(steps) }}）、RUN_URL；data/status.json 有的話一併列出資料狀態。
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"twse": "證交所收盤（tw.json）", "rates": "央行牌告利率（rates.json）", "universe": "上市櫃清單（universe.json）",
         "dividends": "除權息與殖利率（dividends.json）", "holdings": "ETF 持股（etf_holdings.json）",
         "validate": "資料品質檢查", "pages": "GitHub Pages 設定", "deploy": "發佈到 GitHub Pages"}
MARK = {"success": "✅", "failure": "❌", "skipped": "⏭️", "cancelled": "⏹️"}


def report(steps, status=None, run_url=""):
    lines = ["每日資料更新有步驟失敗。抓取失敗時網站會沿用上一份資料；品質檢查沒過則這次不會發佈。", "",
             "| 步驟 | 結果 |", "| --- | --- |"]
    lines += [f"| {NAMES[k]} | {MARK.get(v.get('outcome'), '')} {v.get('outcome', '')} |"
              for k, v in steps.items() if k in NAMES]
    if status:
        bad = [d for d in status.get("datasets", []) if d["state"] != "ok"]
        if bad:
            lines += ["", "**資料狀態**", ""] + [f"- {d['file']}（{d['asof'] or '無日期'}）：{d['note']}" for d in bad]
        if status.get("errors"):
            lines += ["", "**品質檢查錯誤**", ""] + [f"- {e}" for e in status["errors"][:20]]
    if steps.get("pages", {}).get("outcome") == "failure":
        lines += ["", "**網站沒有發佈**：repo 還沒開啟 GitHub Pages。到 Settings → Pages，把 Source 選成「GitHub Actions」，再手動 Run workflow 一次。"]
    lines += ["", f"執行紀錄：{run_url}" if run_url else "",
              "處理方式：看執行紀錄裡失敗那一步的訊息；證交所暫時連不上通常隔天就好，也可以到 Actions 手動 Run workflow 重跑。"]
    return "\n".join(lines)


def main():
    steps = json.loads(os.environ.get("STEPS") or "{}")
    path = ROOT / "data" / "status.json"
    status = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    print(report(steps, status, os.environ.get("RUN_URL", "")))


if __name__ == "__main__":
    main()
