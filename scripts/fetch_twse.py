"""從臺灣證券交易所公開資料產生 data/tw.json，供網頁的六位理專選股使用。

用法：python scripts/fetch_twse.py
輸出：data/tw.json
  {"asof": "YYYY-MM-DD", "dates": [13 個月份日期], "stocks": [
    {"c": 代號, "n": 名稱, "i": 產業別代碼, "p": 收盤, "chg": 漲跌%, "tv": 成交值(億),
     "ma": 月均價, "pe": 本益比, "dy": 殖利率%, "pb": 淨值比, "m": [過去 12 個月的月收盤，舊到新]}]}

資料來源（皆為免費、免金鑰）：
  openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL      個股當日成交
  openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL  個股收盤與月平均價
  openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL         本益比、殖利率、淨值比
  openapi.twse.com.tw/v1/opendata/t187ap03_L               上市公司基本資料（產業別）
  www.twse.com.tw/exchangeReport/MI_INDEX                  指定日期的全市場收盤（取月收盤）
  www.twse.com.tw/rwd/zh/exRight/TWT49U                    除權息計算結果（ETF 配息與還原股價）
個股：成交值超過 1 億元、代號為四碼數字的普通股。
ETF：代號 00 開頭、成交值超過 3000 萬元，另存在 "etfs"，多了 "t"（類型）與 "cd"（近一年配息）。
月收盤 "m" 已依除權息還原，讓報酬與均值不會因配息而失真。
"""

import datetime as dt
import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tw.json"
OPENAPI = "https://openapi.twse.com.tw/v1"
MIN_TV = 1e8
MIN_TV_ETF = 3e7


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "advisor-roundtable/0.1 (research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def roc_date(s):
    y, m, d = re.findall(r"\d+", s)
    return f"{int(y) + 1911}{int(m):02d}{int(d):02d}"


def dividends(start, end):
    """回傳 ({代號: [(除權息日, 還原係數)]}, {代號: 期間內現金股利合計})。"""
    d = get(f"https://www.twse.com.tw/rwd/zh/exRight/TWT49U?response=json&startDate={start}&endDate={end}")
    f = d["fields"]
    di, ci, pre, ref, val, kind = (f.index(k) for k in ("資料日期", "股票代號", "除權息前收盤價", "除權息參考價", "權值+息值", "權/息"))
    events, cash = {}, {}
    for r in d.get("data", []):
        day, code = roc_date(r[di]), r[ci]
        if num(r[pre]) and num(r[ref]):
            events.setdefault(code, []).append((day, num(r[ref]) / num(r[pre])))
        if r[kind] == "息":
            cash[code] = cash.get(code, 0) + (num(r[val]) or 0)
    return events, cash


def etf_type(code, name):
    if code[-1] in "LR" or re.search("正2|反1|反向|槓桿", name):
        return "槓桿反向"
    if code[-1] == "B" or "債" in name:
        return "債券"
    if code[-1] == "U" or re.search("期貨|原油|黃金|白銀|VIX", name):
        return "期貨商品"
    if code[-1] == "A":
        return "主動式高股息" if re.search("高息|股息|收益", name) else "主動式"
    if re.search("美|日本|日經|中國|滬深|印度|越南|全球|標普|S&P|NASDAQ|那斯達克|費城|歐洲|韓|港|上証|恒生|A50", name):
        return "海外"
    if re.search("高息|高股息|股息|優息|收益|紅利|息收", name):
        return "高股息"
    if re.search("台灣50|臺灣50|台50|中型100|MSCI|台灣領袖|臺灣領袖|市值", name):
        return "市值型"
    return "主題型"


def adjust(series, dates, evs):
    """把除權息日之前的價格乘上還原係數。"""
    out = []
    for day, v in zip(dates, series):
        f = 1.0
        for ex, k in evs:
            if day < ex:
                f *= k
        out.append(round(v * f, 2))
    return out


def month_close(day):
    """回傳 {代號: 收盤}；當天休市時回傳空字典。"""
    d = get(f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=ALLBUT0999&date={day:%Y%m%d}")
    for t in d.get("tables", []):
        f = t.get("fields", [])
        if "證券代號" in f and "收盤價" in f:
            ci, pi = f.index("證券代號"), f.index("收盤價")
            return {r[ci]: num(r[pi]) for r in t["data"] if num(r[pi])}
    return {}


def trading_day_near(day):
    """從 day 往後找第一個有收盤資料的交易日。"""
    for ahead in range(7):
        d = day + dt.timedelta(days=ahead)
        closes = month_close(d)
        time.sleep(3)  # 證交所網站有頻率限制
        if closes:
            return d, closes
    raise RuntimeError(f"{day} 後一週都找不到交易資料")


def main():
    day_all = {r["Code"]: r for r in get(f"{OPENAPI}/exchangeReport/STOCK_DAY_ALL")}
    avg = {r["Code"]: r for r in get(f"{OPENAPI}/exchangeReport/STOCK_DAY_AVG_ALL")}
    bw = {r["Code"]: r for r in get(f"{OPENAPI}/exchangeReport/BWIBBU_ALL")}
    ind = {r["公司代號"]: r["產業別"] for r in get(f"{OPENAPI}/opendata/t187ap03_L")}

    # 證交所 OpenAPI 的日期是民國年，例如 1151021
    roc = next(iter(day_all.values()))["Date"]
    asof = dt.date(int(roc[:-4]) + 1911, int(roc[-4:-2]), int(roc[-2:]))
    # 過去 12 個月，每月同一天附近的交易日
    dates, months = [], []
    for k in range(12, 0, -1):
        y, m = divmod(asof.month - 1 - k, 12)
        target = dt.date(asof.year + y, m + 1, min(asof.day, 28))
        d, closes = trading_day_near(target)
        dates.append(f"{d:%Y%m%d}")
        months.append(closes)
    dates.append(f"{asof:%Y%m%d}")

    events, cash = dividends(dates[0], dates[-1])
    stocks, etfs = [], []
    for code, r in day_all.items():
        tv, p = num(r.get("TradeValue")), num(r.get("ClosingPrice"))
        is_etf = code.startswith("00")
        if not (tv and p and tv >= (MIN_TV_ETF if is_etf else MIN_TV)):
            continue
        if not is_etf and not (len(code) == 4 and code.isdigit()):
            continue
        m = [mc.get(code) for mc in months]
        if any(v is None for v in m):
            continue  # 上市未滿一年
        m = adjust(m, dates[:12], [e for e in events.get(code, []) if e[0] > dates[0]])
        seq = m + [p]
        if is_etf and any(not 0.45 < y / x < 2.2 for x, y in zip(seq, seq[1:])):
            continue  # ETF 期間內有分割或反分割，價格無法比較
        chg = num(r.get("Change")) or 0
        row = {
            "c": code, "n": r["Name"], "p": p,
            "chg": round(chg / (p - chg) * 100, 2) if p != chg else 0,
            "tv": round(tv / 1e8, 2),
            "ma": num(avg.get(code, {}).get("MonthlyAveragePrice")) or p,
            "m": m,
        }
        if is_etf:
            c = round(cash.get(code, 0), 3)
            row.update({"i": "ETF", "t": etf_type(code, r["Name"]), "pe": None, "pb": None,
                        "dy": round(c / p * 100, 2), "cd": c})
            etfs.append(row)
        else:
            b = bw.get(code, {})
            row.update({"i": ind.get(code, "20"), "pe": num(b.get("PEratio")),
                        "dy": num(b.get("DividendYield")), "pb": num(b.get("PBratio"))})
            stocks.append(row)
    stocks.sort(key=lambda s: -s["tv"])
    etfs.sort(key=lambda s: -s["tv"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"asof": f"{asof:%Y-%m-%d}", "dates": dates, "stocks": stocks, "etfs": etfs},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ok  個股 {len(stocks)} 檔、ETF {len(etfs)} 檔，資料日 {asof}")


if __name__ == "__main__":
    main()
