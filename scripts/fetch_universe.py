"""抓台灣全部上市、上櫃股票與 ETF 清單，寫入 data/universe.json。

來源（都是官方開放資料）：
- 上市公司基本資料：https://openapi.twse.com.tw/v1/opendata/t187ap03_L
- 上市每日收盤（含 ETF）：https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL
- 上櫃每日收盤（含 ETF）：https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes
- 上櫃證券代號與產業別：https://isin.twse.com.tw/isin/C_public.jsp?strMode=4
用法：python scripts/fetch_universe.py               （線上抓）
      python scripts/fetch_universe.py --raw DIR     （用已下載的 L.json LD.json OD.json isin_O.json）
抓不到或筆數太少就保留舊檔。
"""
import html as H
import json
import re
import sys
import time
from pathlib import Path

import fetch_twse
from net import fetch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "universe.json"

IND = {"01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械", "06": "電器電纜",
       "08": "玻璃陶瓷", "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業", "12": "汽車工業", "14": "建材營造業",
       "15": "航運業", "16": "觀光餐旅", "17": "金融保險業", "18": "貿易百貨業", "20": "其他業", "21": "化學工業",
       "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業",
       "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業",
       "32": "文化創意業", "33": "農業科技業", "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
       "91": "存託憑證"}
FOREIGN = re.compile(r"美|日|全球|中國|滬深|上證|上証|深證|深証|深100|中証|A50|恒生|香港|歐洲|印度|越南|韓|新興|亞|那斯達克|納斯達克|NASDAQ|S&P|費城|道瓊|德國|英國|澳洲|東協|國際|世界|特選|MSCI A|MSCI中國|標普|FANG|ETF\+|機器人|元宇宙|基因|潔淨|資安|電池|未來車|電動車")


def get(url):
    return fetch(url)


def isin_rows(raw):
    page = raw.decode("big5", "replace") if isinstance(raw, bytes) else raw
    out, sec = [], None
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        tds = [H.unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(tds) == 1:
            sec = tds[0]
        elif len(tds) >= 7 and sec:
            out.append([sec] + tds)
    return out


def f(s):
    try:
        return float(str(s).replace(",", "").replace("+", ""))
    except ValueError:
        return None


def etf_type(code, name):
    if code.endswith("L") or code.endswith("R") or "正2" in name or "反1" in name:
        return "槓桿反向"
    if code.endswith("U") or name.startswith("期"):
        return "商品期貨"
    if code.endswith("B") or "債" in name:
        return "債券"
    if code.endswith("A") or name.startswith("主動"):
        return "主動式"
    if re.search(r"高息|高股息|股利|收益|息", name):
        return "高股息"
    bare = name.replace("台新", "")
    if FOREIGN.search(bare) and not re.search(r"^(台|臺)|台灣|臺灣|台股|臺股|台精|臺韓", bare):
        return "海外股票"
    return "指數／主題"


def build(L, LD, OD, IO):
    q = {x["Code"]: x for x in LD}
    stocks, etfs = [], []
    for c in L:
        k = c["公司代號"].strip()
        p = q.get(k, {})
        stocks.append([k, c["公司簡稱"].strip(), "上市", IND.get(c["產業別"], "其他業"), f(p.get("ClosingPrice")),
                       f(p.get("Change")), round((f(p.get("TradeValue")) or 0) / 1e8, 2), c.get("上市日期", "")[:4],
                       round((f(c.get("實收資本額")) or 0) / 1e8, 1)])
    for x in LD:
        k = x["Code"]
        if k.startswith("00"):
            etfs.append([k, x["Name"], "上市", etf_type(k, x["Name"]), f(x["ClosingPrice"]), f(x["Change"]),
                         round((f(x["TradeValue"]) or 0) / 1e8, 2)])
    oq = {x["SecuritiesCompanyCode"]: x for x in OD}
    for r in IO:
        code, _, name = r[1].partition("　")
        code, name = code.strip(), name.strip()
        p = oq.get(code, {})
        if r[0] == "股票":
            stocks.append([code, name, "上櫃", r[5].strip() or "其他業", f(p.get("Close")), f(p.get("Change")),
                           round((f(p.get("TransactionAmount")) or 0) / 1e8, 2), r[3][:4],
                           round((f(p.get("Capitals")) or 0) / 1e8, 1)])
        elif r[0] == "ETF":
            etfs.append([code, name, "上櫃", etf_type(code, name), f(p.get("Close")), f(p.get("Change")),
                         round((f(p.get("TransactionAmount")) or 0) / 1e8, 2)])
    stocks.sort(key=lambda s: s[0])
    etfs.sort(key=lambda s: s[0])
    return {"asof": time.strftime("%Y-%m-%d"),
            "cols": {"stock": ["代號", "名稱", "市場", "產業", "收盤", "漲跌", "成交值億", "上市年", "股本億"],
                     "etf": ["代號", "名稱", "市場", "類型", "收盤", "漲跌", "成交值億"]},
            "stock": stocks, "etf": etfs}


def main():
    raw = len(sys.argv) == 3 and sys.argv[1] == "--raw"
    try:
        if raw:
            d = Path(sys.argv[2])
            L, LD, OD, IO = (json.loads((d / n).read_text(encoding="utf-8")) for n in
                             ("L.json", "LD.json", "OD.json", "isin_O.json"))
        else:
            L = json.loads(get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L"))
            LD, asof, _ = fetch_twse.latest_day_all()  # OpenAPI 停更時改用證交所網站
            OD = json.loads(get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"))
            IO = isin_rows(get("https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"))
        u = build(L, LD, OD, IO)
        if not raw:
            u["asof"] = f"{asof:%Y-%m-%d}"  # 上市收盤的資料日，不是執行日
        if len(u["stock"]) < 1500 or len(u["etf"]) < 150:
            raise ValueError(f"筆數太少：股票 {len(u['stock'])}、ETF {len(u['etf'])}")
    except Exception as e:  # noqa: BLE001
        print(f"warn: universe 未更新，保留舊檔（{e}）")
        return
    OUT.write_text(json.dumps(u, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"universe: 股票 {len(u['stock'])}、ETF {len(u['etf'])}")


if __name__ == "__main__":
    main()
