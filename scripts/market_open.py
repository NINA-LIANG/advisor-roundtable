"""判斷今天（台北時間）台股有沒有開市，休市日就跳過每日更新。

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

from net import fetch

URL = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
TPE = dt.timezone(dt.timedelta(hours=8))


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
    today = dt.datetime.now(TPE).date()
    try:
        closed = closed_days(json.loads(fetch(URL, waits=(2, 4))))
        why = "休市日" if today in closed else ""
    except Exception as e:  # noqa: BLE001
        print(f"warn  抓不到休市表，當作有開市：{e}", file=sys.stderr)
        closed, why = set(), ""
    ok = is_open(today, closed)
    print(f"{today} {'開市' if ok else '休市（' + (why or '週末') + '），跳過今天的更新'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"open={'true' if ok else 'false'}\n")


if __name__ == "__main__":
    main()
