"""判斷這次排程該更新的交易日台股有沒有開市，休市日就跳過每日更新。

GitHub 的排程常延後 5～10 小時（2026-10 實測台灣時間 00:45～04:27 才跑），星期五的更新拖到
星期六凌晨會被誤判成週末而跳過（10/30 的資料就是這樣漏掉）。所以「該更新哪一天」用執行時間往前推
12 小時的台北日期：18:47 準時跑仍是當天，隔天 04:27 才跑也算前一天。
另有晚上的備援排程：若 data/tw.json 已經是這個交易日的資料，代表前一次排程已經跑完，就跳過。

用法：python scripts/market_open.py          印出 open=true／false；在 GitHub Actions 裡同時寫進 $GITHUB_OUTPUT
資料來源：openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule（證交所市場開休市日期）
  清單裡除了放假日，也有「開始交易」「最後交易」這類照常開市的日子，名稱或說明裡有「交易」的不算休市。
  抓不到休市表時當作有開市：寧可多跑一次（資料沒變就不會提交），也不要漏掉一天。
"""

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

from net import fetch

URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
TPE = dt.timezone(dt.timedelta(hours=8))
LATE = dt.timedelta(hours=12)  # 排程最多延後多久仍算同一個交易日
ROOT = Path(__file__).resolve().parent.parent


def trade_day(now=None):
    """這次排程該更新的交易日（台北日期）"""
    now = now or dt.datetime.now(TPE)
    return (now.astimezone(TPE) - LATE).date()


def already_done(day, root=ROOT):
    """tw.json 已經是這一天的收盤資料：前一個排程已經更新過"""
    try:
        return json.loads((root / "data" / "tw.json").read_text(encoding="utf-8")).get("asof") == day.isoformat()
    except (OSError, ValueError):
        return False


def to_date(s):
    """證交所日期可能是民國 1150101、115/01/01 或西元 20260101"""
    n = re.findall(r"\d+", str(s))
    if len(n) == 1 and len(n[0]) in (7, 8):
        s = n[0]
        y, m, d = (int(s[:-4]), int(s[-4:-2]), int(s[-2:]))
    elif len(n) == 3:
        y, m, d = map(int, n)
    else:
        return None
    return dt.date(y + 1911 if y < 1911 else y, m, d)


def closed_days(rows):
    out = set()
    for r in rows:
        day = to_date(r.get("Date") or r.get("日期") or "")
        text = f"{r.get('Name') or r.get('名稱') or ''}{r.get('Description') or r.get('說明') or ''}"
        if day and "交易" not in text:
            out.add(day)
    return out


def is_open(day, closed):
    return day.weekday() < 5 and day not in closed


def main():
    today = trade_day()
    try:
        closed = closed_days(json.loads(fetch(URL, waits=(2, 4))))
        why = "休市日" if today in closed else ""
    except Exception as e:  # noqa: BLE001
        print(f"warn  抓不到休市表，當作有開市：{e}", file=sys.stderr)
        closed, why = set(), ""
    ok = is_open(today, closed)
    if ok and already_done(today):
        ok = False
        print(f"{today} 開市，但 tw.json 已經是這一天的資料（前一次排程已更新），這次跳過")
    else:
        print(f"{today} {'開市' if ok else '休市（' + (why or '週末') + '），跳過這次更新'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"open={'true' if ok else 'false'}\n")


if __name__ == "__main__":
    main()
