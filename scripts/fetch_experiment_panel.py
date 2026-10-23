"""抓論文實驗用的歷史資料（2022-07～2025-03），整理成 knowledge/experiment/panel.json。

只需要跑一次（之後題庫就凍結）。證交所網站有頻率限制，每次請求間隔 3 秒，全部約 25 分鐘；
抓過的回應存在 .cache/twse/，中斷後重跑會從快取接著做。
這個開發環境連不到證交所，請用 GitHub Actions 的 build-experiment 流程執行。

用法：python scripts/fetch_experiment_panel.py
輸出 panel.json：
  {"decision_dates": [18 個決策日 YYYYMMDD], "month_ends": {"YYYY-MM": "YYYYMMDD"},
   "stocks": {代號: {"n": 名稱, "i": 產業別, "close": {日期: 收盤}, "avg": {"YYYY-MM": 月均價},
                     "tv": {決策日: 成交值(億)}, "bw": {決策日: [本益比, 殖利率, 淨值比]}}},
   "events": {代號: [[除權息日, 還原係數]]}}
價格都是原始收盤，除權息還原在 build_experiment_items.py 做。
"""

import datetime as dt
import json
import time
from pathlib import Path

from fetch_twse import dividends, get, num

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "knowledge" / "experiment" / "panel.json"
CACHE = ROOT / ".cache" / "twse"
FIRST_DECISION, LAST_DECISION = (2023, 7), (2024, 12)
HISTORY, HORIZON = 12, 3  # 決策日前 12 個月的月收盤、之後 3 個月的結果
MIN_TV = 1e8
BENCH = "0050"


def months(start, n):
    y, m = start
    for k in range(n):
        yy, mm = divmod(m - 1 + k, 12)
        yield y + yy, mm + 1


def shift(ym, k):
    y, m = divmod(ym[0] * 12 + ym[1] - 1 + k, 12)
    return y, m + 1


def cached(name, url):
    path = CACHE / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    data = get(url)
    time.sleep(3)  # 證交所網站有頻率限制
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def day_table(day):
    """{代號: (名稱, 收盤, 成交金額)}；休市日回傳空字典"""
    d = cached(f"MI_INDEX_{day:%Y%m%d}.json",
               f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=ALLBUT0999&date={day:%Y%m%d}")
    for t in d.get("tables", []):
        f = t.get("fields", [])
        if "證券代號" in f and "收盤價" in f:
            ci, ni, pi, vi = (f.index(k) for k in ("證券代號", "證券名稱", "收盤價", "成交金額"))
            return {r[ci]: (r[ni].strip(), num(r[pi]), num(r[vi]) or 0) for r in t["data"] if num(r[pi])}
    return {}


def bwibbu(day):
    d = cached(f"BWIBBU_{day:%Y%m%d}.json",
               f"https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&selectType=ALL&date={day:%Y%m%d}")
    f = d.get("fields", [])
    if not f:
        return {}
    ci, yi, pi, bi = (f.index(k) for k in ("證券代號", "殖利率(%)", "本益比", "股價淨值比"))
    return {r[ci]: [num(r[pi]), num(r[yi]), num(r[bi])] for r in d.get("data", [])}


def last_trading_day(y, m):
    """當月最後一個交易日與當天行情"""
    day = dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1)
    for _ in range(10):
        if day.weekday() < 5:
            t = day_table(day)
            if t:
                return day, t
        day -= dt.timedelta(days=1)
    raise RuntimeError(f"{y}-{m:02d} 找不到交易日")


def keep(code):
    return (len(code) == 4 and code.isdigit()) or code == BENCH


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    n_dec = (LAST_DECISION[0] - FIRST_DECISION[0]) * 12 + LAST_DECISION[1] - FIRST_DECISION[1] + 1
    decision_months = list(months(FIRST_DECISION, n_dec))
    all_months = list(months(shift(FIRST_DECISION, -HISTORY), n_dec + HISTORY + HORIZON))
    ind = {r["公司代號"]: r["產業別"] for r in get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")}
    stocks, month_ends, decision_dates = {}, {}, []

    def put(code, name):
        return stocks.setdefault(code, {"n": name, "i": ind.get(code, "ETF" if code == BENCH else ""),
                                        "close": {}, "avg": {}, "tv": {}, "bw": {}})

    for y, m in all_months:
        key = f"{y}-{m:02d}"
        if (y, m) in decision_months:
            # 決策月：每個交易日都抓，才能算月均價
            day, daily = dt.date(y, m, 1), []
            while day.month == m:
                if day.weekday() < 5:
                    t = day_table(day)
                    if t:
                        daily.append((day, t))
                day += dt.timedelta(days=1)
            end, table = daily[-1]
            for code in table:
                if keep(code):
                    vals = [t[code][1] for _, t in daily if code in t]
                    put(code, table[code][0])["avg"][key] = round(sum(vals) / len(vals), 2)
            ds = f"{end:%Y%m%d}"
            decision_dates.append(ds)
            bw = bwibbu(end)
            for code, (name, close, value) in table.items():
                if keep(code):
                    s = put(code, name)
                    s["tv"][ds] = round(value / 1e8, 2)
                    if code in bw:
                        s["bw"][ds] = bw[code]
        else:
            end, table = last_trading_day(y, m)
        ds = f"{end:%Y%m%d}"
        month_ends[key] = ds
        for code, (name, close, _) in table.items():
            if keep(code):
                put(code, name)["close"][ds] = close
        print(f"ok  {key}（{ds}，{len(table)} 檔）", flush=True)

    # 只留下至少一個決策日成交值超過 1 億元的股票（以及 0050）
    stocks = {c: s for c, s in stocks.items()
              if c == BENCH or any(v * 1e8 >= MIN_TV for v in s["tv"].values())}
    events = {}
    first, last = all_months[0], all_months[-1]
    for y, m in months(first, (last[0] - first[0]) * 12 + last[1] - first[1] + 1):
        if m % 3 == 1:  # 一季抓一次，避免單次範圍太大
            end = dt.date(y + (m + 2) // 12, (m + 2) % 12 + 1, 1) - dt.timedelta(days=1)
            ev, _ = dividends(f"{y}{m:02d}01", f"{end:%Y%m%d}")
            time.sleep(3)
            for code, rows in ev.items():
                if code in stocks:
                    events.setdefault(code, []).extend([d, round(k, 6)] for d, k in rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"source": "臺灣證券交易所 MI_INDEX、BWIBBU_d、TWT49U、t187ap03_L",
                               "fetched": f"{dt.date.today()}", "decision_dates": decision_dates,
                               "month_ends": month_ends, "stocks": stocks, "events": events},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ok  {OUT.relative_to(ROOT)}（{len(stocks)} 檔、{len(decision_dates)} 個決策日）")


if __name__ == "__main__":
    main()
