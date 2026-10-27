"""從臺灣證券交易所公開資料產生 data/tw.json，供網頁的六位理專選股使用。

用法：python scripts/fetch_twse.py
輸出：data/tw.json
  {"asof": "YYYY-MM-DD", "dates": [13 個月份日期], "stocks": [
    {"c": 代號, "n": 名稱, "i": 產業別代碼, "p": 收盤, "chg": 漲跌%, "tv": 成交值(億),
     "ma": 月均價, "pe": 本益比, "dy": 殖利率%, "pb": 淨值比, "m": [過去 12 個月的月收盤，舊到新]}],
   "ind_pe": {產業別代碼: {"med": 中位數, "n": 檔數}}, "mkt_pe": 全市場本益比中位數}

資料來源（皆為免費、免金鑰）：
  openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL      個股當日成交
  openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_AVG_ALL  個股收盤與月平均價
  openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL         本益比、殖利率、淨值比
  openapi.twse.com.tw/v1/opendata/t187ap03_L               上市公司基本資料（產業別）
  www.twse.com.tw/exchangeReport/MI_INDEX                  指定日期的全市場收盤（取月收盤）
  www.twse.com.tw/rwd/zh/exRight/TWT49U                    除權息計算結果（ETF 配息與還原股價）
  www.twse.com.tw/exchangeReport/BWIBBU_d                  指定日期的本益比、殖利率、淨值比
OpenAPI 偶爾會停在某一天好幾天不更新（2026-10 曾停在 10/22），這時改用證交所網站的 MI_INDEX、BWIBBU_d 補上最新交易日。
個股：成交值超過 1 億元、代號為四碼數字的普通股。
同業本益比中位數（ind_pe、mkt_pe）用全部上市普通股計算，不受成交值門檻影響；成交值門檻只決定推薦名單，
不決定比較基準，否則同一產業的樣本會隨每天的成交量變動（例：汽車類曾只剩兩檔，取到 341 倍那一檔）。
ETF：代號 00 開頭、成交值超過 3000 萬元，另存在 "etfs"，多了 "t"（類型）與 "cd"（近一年配息）。
月收盤 "m" 已依除權息還原，讓報酬與均值不會因配息而失真。
"""

import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

from net import fetch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tw.json"
OPENAPI = "https://openapi.twse.com.tw/v1"
MIN_TV = 1e8
MIN_TV_ETF = 3e7
MIN_STOCKS = 200  # 平常約 320 檔
MIN_ETFS = 20  # 平常約 80 檔
TPE = dt.timezone(dt.timedelta(hours=8))


def get(url):
    return json.loads(fetch(url).decode("utf-8"))


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


def median(a):
    b = sorted(a)
    m = len(b) // 2
    return b[m] if len(b) % 2 else (b[m - 1] + b[m]) / 2


def peer_pe(bw, ind):
    """全部上市普通股（四碼數字、本益比大於 0）的產業本益比中位數與全市場中位數。"""
    groups, every = {}, []
    for code, r in bw.items():
        pe = num(r.get("PEratio"))
        if code.startswith("00") or not (len(code) == 4 and code.isdigit() and pe and pe > 0):
            continue
        groups.setdefault(ind.get(code, "20"), []).append(pe)
        every.append(pe)
    ind_pe = {k: {"med": round(median(v), 2), "n": len(v)} for k, v in sorted(groups.items())}
    return ind_pe, (round(median(every), 2) if every else None)


def close_table(day):
    """證交所網站某天的全市場收盤表，回傳 (欄位, 資料列)；當天休市回傳 ([], [])。"""
    d = get(f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=ALLBUT0999&date={day:%Y%m%d}")
    for t in d.get("tables", []):
        f = t.get("fields", [])
        if "證券代號" in f and "收盤價" in f:
            return f, t.get("data", [])
    return [], []


def month_close(day):
    """回傳 {代號: 收盤}；當天休市時回傳空字典。"""
    f, rows = close_table(day)
    if not f:
        return {}
    ci, pi = f.index("證券代號"), f.index("收盤價")
    return {r[ci]: num(r[pi]) for r in rows if num(r[pi])}


def site_day_all(day):
    """把網站收盤表轉成和 OpenAPI STOCK_DAY_ALL 一樣的欄位；休市回傳空串列。"""
    f, rows = close_table(day)
    if not f:
        return []
    ci, ni, vi, pi, si, di = (f.index(k) for k in ("證券代號", "證券名稱", "成交金額", "收盤價", "漲跌(+/-)", "漲跌價差"))
    roc = f"{day.year - 1911}{day:%m%d}"
    out = []
    for r in rows:
        sign = "-" if "-" in re.sub(r"<[^>]*>", "", str(r[si])) else ""
        out.append({"Code": r[ci].strip(), "Name": r[ni].strip(), "TradeValue": str(r[vi]).replace(",", ""),
                    "ClosingPrice": str(r[pi]).replace(",", ""), "Change": sign + str(r[di]).replace(",", ""),
                    "Date": roc})
    return out


def site_bwibbu(day):
    """證交所網站某天的本益比、殖利率、淨值比，欄位名稱和 OpenAPI BWIBBU_ALL 相同。"""
    d = get(f"https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&date={day:%Y%m%d}&selectType=ALL")
    f = d.get("fields", [])
    if not d.get("data") or "證券代號" not in f:
        return {}
    col = {k: next(i for i, x in enumerate(f) if k in x) for k in ("證券代號", "殖利率", "本益比", "淨值比")}
    return {r[col["證券代號"]].strip(): {"PEratio": r[col["本益比"]], "DividendYield": r[col["殖利率"]],
                                       "PBratio": r[col["淨值比"]]} for r in d["data"]}


def roc_to_date(roc):
    """證交所 OpenAPI 的日期是民國年，例如 1151021"""
    return dt.date(int(roc[:-4]) + 1911, int(roc[-4:-2]), int(roc[-2:]))


def latest_day_all(today=None):
    """回傳 (上市全部收盤列, 資料日, 是否改用網站)。OpenAPI 比今天舊時，往回找網站上較新的交易日。"""
    rows = get(f"{OPENAPI}/exchangeReport/STOCK_DAY_ALL")
    asof = roc_to_date(rows[0]["Date"])
    today = today or dt.datetime.now(TPE).date()
    for back in range((today - asof).days):
        day = today - dt.timedelta(days=back)
        try:
            site = site_day_all(day)
        except Exception as e:  # noqa: BLE001  網站連不上就用 OpenAPI 的
            print(f"warn  證交所網站 {day} 收盤抓取失敗：{e}", file=sys.stderr)
            break
        time.sleep(3)  # 證交所網站有頻率限制
        if site:
            print(f"note  OpenAPI 停在 {asof}，改用證交所網站 {day} 的收盤", file=sys.stderr)
            return site, day, True
    return rows, asof, False


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
    rows, asof, from_site = latest_day_all()
    day_all = {r["Code"]: r for r in rows}
    avg = {r["Code"]: r for r in get(f"{OPENAPI}/exchangeReport/STOCK_DAY_AVG_ALL")}
    bw = {r["Code"]: r for r in get(f"{OPENAPI}/exchangeReport/BWIBBU_ALL")}
    if from_site:
        try:
            bw = site_bwibbu(asof) or bw
        except Exception as e:  # noqa: BLE001
            print(f"warn  證交所網站本益比抓取失敗，沿用 OpenAPI：{e}", file=sys.stderr)
    ind = {r["公司代號"]: r["產業別"] for r in get(f"{OPENAPI}/opendata/t187ap03_L")}
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
    # 證交所偶爾回空表或欄位改名；筆數不對或日期倒退就不覆蓋，網站繼續用上一份好資料
    prev = json.loads(OUT.read_text(encoding="utf-8")).get("asof", "") if OUT.exists() else ""
    if len(stocks) < MIN_STOCKS or len(etfs) < MIN_ETFS:
        sys.exit(f"fail  筆數太少（個股 {len(stocks)}、ETF {len(etfs)}），保留舊檔 {prev}")
    if f"{asof:%Y-%m-%d}" < prev:
        sys.exit(f"fail  資料日 {asof} 比舊檔 {prev} 還舊，保留舊檔")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ind_pe, mkt_pe = peer_pe(bw, ind)
    OUT.write_text(json.dumps({"asof": f"{asof:%Y-%m-%d}", "dates": dates, "stocks": stocks, "etfs": etfs,
                               "ind_pe": ind_pe, "mkt_pe": mkt_pe},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ok  個股 {len(stocks)} 檔、ETF {len(etfs)} 檔，資料日 {asof}")


if __name__ == "__main__":
    main()
