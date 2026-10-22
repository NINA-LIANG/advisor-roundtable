"""抓除權息預告、近期除權息結果與殖利率，寫入 data/dividends.json。

來源（都是官方開放資料）：
- 上市除權息預告：https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL
- 上櫃除權息預告：https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost
- 上市除權息結果（近 45 天）：https://www.twse.com.tw/rwd/zh/exRight/TWT49U
- 上櫃除權息結果（當天）：https://www.tpex.org.tw/openapi/v1/tpex_exright_daily（每天累積進舊檔）
- 上市殖利率／本益比／淨值比：https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL
- 上櫃殖利率／本益比／淨值比：https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis
- ETF 近一年配息：沿用 data/tw.json 的 cd（fetch_twse.py 由 TWT49U 算出）
用法：python scripts/fetch_dividends.py             （線上抓）
      python scripts/fetch_dividends.py --raw DIR   （用已下載的 twt48u tpex_ex twt49u tpex_exd bwibbu tpex_pe .json）
任何一個來源抓不到就沿用舊檔該部分。
"""
import datetime as dt
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dividends.json"
KEEP_DAYS = 60


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def f(s):
    try:
        v = float(str(s).replace(",", ""))
    except ValueError:
        return None
    return v


def roc(s):
    """1151022 或 115年10月22日 → 2026-10-22"""
    n = re.findall(r"\d+", str(s))
    if len(n) == 1 and len(n[0]) == 7:
        n = [n[0][:3], n[0][3:5], n[0][5:]]
    y, m, d = (int(x) for x in n[:3])
    return f"{y + 1911:04d}-{m:02d}-{d:02d}"


def kind(s):
    s = s.replace("除", "")
    return {"息": "息", "權": "權", "權息": "權息"}.get(s, s)


def upcoming(L, O):
    out = []
    for x in L:
        cash = f(x.get("CashDividend")) if x.get("CashDividend") else None
        out.append([roc(x["Date"]), x["Code"], x["Name"].strip(), "上市", kind(x["Exdividend"]), cash,
                    f(x.get("StockDividendRatio")) or None])
    for x in O:
        cash = f(x.get("CashDividend"))
        out.append([roc(x["ExRrightsExDividendDate"]), x["SecuritiesCompanyCode"], x["CompanyName"].strip(), "上櫃",
                    kind(x["ExRrightsExDividend"]), cash, f(x.get("StockDividendRatio")) or None])
    out.sort(key=lambda r: (r[0], r[1]))
    return out


def results(L, O, old):
    """[日期, 代號, 名稱, 市場, 權/息, 除權息前收盤, 參考價, 權值+息值]"""
    rows = {(r[0], r[1]): r for r in old}
    for x in L.get("data", []):
        rows[(roc(x[0]), x[1])] = [roc(x[0]), x[1], x[2].strip(), "上市", kind(x[6]), f(x[3]), f(x[4]), f(x[5])]
    for x in O:
        k = (roc(x["Date"]), x["SecuritiesCompanyCode"])
        rows[k] = [k[0], k[1], x["CompanyName"].strip(), "上櫃", kind(x["ExRightsDiviend"]),
                   f(x["ClosePriceBeforeExRightsDiviend"]), f(x["ExRightsDiviendQuote"]),
                   f(x["StockDividendPlusCashDividend"])]
    cut = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    return sorted((r for r in rows.values() if r[0] >= cut), key=lambda r: (r[0], r[1]), reverse=True)


def yields(L, O):
    """[代號, 名稱, 市場, 殖利率%, 本益比, 淨值比]"""
    out = [[x["Code"], x["Name"].strip(), "上市", f(x["DividendYield"]), f(x["PEratio"]), f(x["PBratio"])] for x in L]
    out += [[x["SecuritiesCompanyCode"], x["CompanyName"].strip(), "上櫃", f(x["YieldRatio"]),
             f(x["PriceEarningRatio"]), f(x["PriceBookRatio"])] for x in O]
    return [r for r in out if r[3] is not None]


def etf_yields():
    """[代號, 名稱, 類型, 近一年配息, 收盤]"""
    tw = json.loads((ROOT / "data" / "tw.json").read_text(encoding="utf-8"))
    return [[e["c"], e["n"], e["t"], e["cd"], e["p"]] for e in tw.get("etfs", []) if e.get("cd") and e.get("p")]


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if len(sys.argv) == 3 and sys.argv[1] == "--raw":
        d = Path(sys.argv[2])
        load = {n: (lambda n=n: json.loads((d / f"{n}.json").read_text(encoding="utf-8")))
                for n in ("twt48u", "tpex_ex", "twt49u", "tpex_exd", "bwibbu", "tpex_pe")}
    else:
        end = dt.date.today()
        start = end - dt.timedelta(days=45)
        urls = {"twt48u": "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL",
                "tpex_ex": "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost",
                "twt49u": "https://www.twse.com.tw/rwd/zh/exRight/TWT49U?response=json"
                          f"&startDate={start:%Y%m%d}&endDate={end:%Y%m%d}",
                "tpex_exd": "https://www.tpex.org.tw/openapi/v1/tpex_exright_daily",
                "bwibbu": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
                "tpex_pe": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"}
        load = {n: (lambda u=u: get(u)) for n, u in urls.items()}

    def part(name, fn, check):
        try:
            v = fn()
            if not check(v):
                raise ValueError("筆數太少")
            return v
        except Exception as e:  # noqa: BLE001
            print(f"warn: {name} 未更新，沿用舊資料（{e}）")
            return old.get(name, [])

    up = part("up", lambda: upcoming(load["twt48u"](), load["tpex_ex"]()), lambda v: len(v) >= 5)
    past = part("past", lambda: results(load["twt49u"](), load["tpex_exd"](), old.get("past", [])),
                lambda v: len(v) >= 5)
    yld = part("yld", lambda: yields(load["bwibbu"](), load["tpex_pe"]()), lambda v: len(v) >= 1000)
    ety = part("etf", etf_yields, lambda v: len(v) >= 10)
    out = {"asof": time.strftime("%Y-%m-%d"),
           "cols": {"up": ["除權息日", "代號", "名稱", "市場", "權/息", "現金股利", "配股率"],
                    "past": ["除權息日", "代號", "名稱", "市場", "權/息", "除權息前收盤", "參考價", "權值+息值"],
                    "yld": ["代號", "名稱", "市場", "殖利率%", "本益比", "淨值比"],
                    "etf": ["代號", "名稱", "類型", "近一年配息", "收盤"]},
           "up": up, "past": past, "yld": yld, "etf": ety}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"dividends: 預告 {len(up)}、近期結果 {len(past)}、殖利率 {len(yld)}、ETF {len(ety)}")


if __name__ == "__main__":
    main()
