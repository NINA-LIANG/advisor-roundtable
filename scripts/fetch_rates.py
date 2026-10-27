"""從中央銀行「牌告利率資訊網」更新 data/rates.json 的各銀行新臺幣存款牌告利率。

用法：python scripts/fetch_rates.py
資料來源：https://cpx.cbc.gov.tw/BIRWEB/（央行彙整各金融機構每日申報的牌告利率，免金鑰）

rates.json 的格式：
  {"asof": "YYYY-MM-DD", "banks": [
    {"n": 銀行名稱, "k": 公股/民營/純網銀/外商/郵局, "src": 來源網址,
     "d":  {"活期": %, "活儲": %, "薪轉": %},
     "td": {月數: [固定, 機動]},   定期存款
     "ts": {月數: [固定, 機動]}}], 定期儲蓄存款
   "promos": [...]}                 優利專案（人工整理，不會被這支程式改動）

央行網站的表頭是多層的（存款種類 × 存期 × 額度 × 固定/機動），這裡把每一欄的各層標題串起來，
再用關鍵字對應到 d/td/ts。抓到的原始回應另存 data/raw/cbc_rates.json，對不上時可以拿來除錯。
任何一步失敗都只印警告、保留舊資料，不讓每日更新整個中斷。
"""

import datetime as dt
import json
import re
import sys
from pathlib import Path

from net import fetch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "rates.json"
RAW = ROOT / "data" / "raw" / "cbc_rates.json"
BASE = "https://cpx.cbc.gov.tw/BIRWEB"
CATEGORIES = ["本國銀行", "外國及大陸銀行在台分行"]
TERMS = {"一個月": "1", "1個月": "1", "三個月": "3", "3個月": "3", "六個月": "6", "6個月": "6",
         "九個月": "9", "9個月": "9", "一年": "12", "1年": "12", "二年": "24", "2年": "24",
         "三年": "36", "3年": "36"}
# 央行名稱和網頁上用的簡稱不同時，以這張表對回 rates.json 的名稱
ALIAS = {"臺灣銀行": "臺灣銀行", "臺灣土地銀行": "臺灣土地銀行", "合作金庫商業銀行": "合作金庫",
         "第一商業銀行": "第一銀行", "華南商業銀行": "華南銀行", "彰化商業銀行": "彰化銀行",
         "兆豐國際商業銀行": "兆豐銀行", "中華郵政": "中華郵政", "國泰世華商業銀行": "國泰世華",
         "中國信託商業銀行": "中國信託", "台北富邦商業銀行": "台北富邦", "玉山商業銀行": "玉山銀行",
         "台新國際商業銀行": "台新銀行", "連線商業銀行": "LINE Bank", "樂天國際商業銀行": "樂天銀行",
         "將來商業銀行": "將來銀行", "陽信商業銀行": "陽信銀行", "新光商業銀行": "新光銀行",
         "台中商業銀行": "台中商銀", "王道商業銀行": "王道銀行", "永豐商業銀行": "永豐銀行",
         "臺灣中小企業銀行": "台灣企銀", "凱基商業銀行": "凱基銀行", "遠東國際商業銀行": "遠東銀行",
         "三信商業銀行": "三信商銀", "上海商業儲蓄銀行": "上海銀行", "聯邦商業銀行": "聯邦銀行",
         "華泰商業銀行": "華泰商銀", "星展(台灣)商業銀行": "星展銀行", "瑞興商業銀行": "瑞興商銀",
         "安泰商業銀行": "安泰銀行", "板信商業銀行": "板信商銀", "元大商業銀行": "元大銀行",
         "高雄銀行": "高雄銀行", "全國農業金庫": "農業金庫", "滙豐(台灣)商業銀行": "匯豐銀行",
         "渣打國際商業銀行": "渣打銀行"}
PUBLIC = {"臺灣銀行", "臺灣土地銀行", "合作金庫", "第一銀行", "華南銀行", "彰化銀行", "兆豐銀行",
          "台灣企銀", "高雄銀行", "農業金庫"}


def post(path, body):
    raw = fetch(f"{BASE}/{path}", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"})
    return json.loads(raw.decode("utf-8"))


def num(x):
    try:
        return float(re.sub(r"<[^>]+>|,", "", str(x)).strip())
    except ValueError:
        return None


def short(name):
    name = re.sub(r"股份有限公司|<[^>]+>", "", name).strip()
    return ALIAS.get(name, name)


def bank_names():
    body = {"range": {"values": [{"key": "銀行類別", "value": CATEGORIES}]}}
    d = post("Range/GetJsonBirData", body)
    # 回傳可能是 {"values": [...]} 或直接是名稱陣列，兩種都接受
    vals = d.get("values", d) if isinstance(d, dict) else d
    names = []
    for v in vals if isinstance(vals, list) else []:
        names.append(v if isinstance(v, str) else v.get("value") or v.get("data") or v.get("text"))
    return [n for n in names if n]


def columns(header_set):
    """把多層表頭展開成每一欄的完整標題，例如「定期存款 一年 一般 機動利率(%)」。"""
    levels = [[c["data"] for c in header_set[k]] for k in header_set if k.startswith("Table")]
    cols = [""]
    for level in levels:
        cols = [f"{c} {x}".strip() for c in cols for x in level]
    return cols


def classify(label):
    """欄位標題 → (區塊, 鍵, 固定0/機動1)；不需要的欄回傳 None。"""
    if re.search(r"大額|300萬|500萬|五百萬|三百萬|證券|外資|支票", label):
        return None
    if re.search(r"一般|^[^額]*$", label) is None:
        return None
    rate = 1 if "機動" in label else 0 if "固定" in label else 1
    if "薪" in label:
        return ("d", "薪轉", 1)
    if "活期儲蓄" in label:
        return ("d", "活儲", 1)
    if "活期存款" in label:
        return ("d", "活期", 1)
    term = next((m for t, m in TERMS.items() if t in label), None)
    if term is None:
        return None
    if "定期儲蓄" in label:
        return ("ts", term, rate)
    if "定期存款" in label or "定期儲金" in label:
        return ("td", term, rate)
    return None


def parse(resp):
    cols = columns(resp.get("headerSet", {}))
    rows = resp.get("data") or []
    if not rows and resp.get("htmlData"):
        rows = [re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
                for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", resp["htmlData"], re.S)]
    found = {}
    for row in rows:
        cells = list(row.values()) if isinstance(row, dict) else list(row)
        # 第一格是列標題（銀行名稱），其餘依序對應展開後的欄位
        name, vals = short(str(cells[0])), cells[1:]
        if len(vals) != len(cols):
            vals = cells[-len(cols):] if len(cells) >= len(cols) else vals
        b = found.setdefault(name, {"d": {}, "td": {}, "ts": {}})
        for label, v in zip(cols, vals):
            hit, x = classify(label), num(v)
            if hit is None or x is None:
                continue
            part, key, i = hit
            if part == "d":
                b["d"][key] = x
            else:
                b[part].setdefault(key, [None, None])[i] = x
    return {k: v for k, v in found.items() if v["d"] or v["td"] or v["ts"]}


def main():
    old = json.loads(OUT.read_text(encoding="utf-8"))
    try:
        names = bank_names()
        resp = post("Data/GetJsonFromArray", {"_range": {"values": [{"key": "銀行名稱", "value": names}]},
                                              "BeginDate": None, "EndDate": None, "RateSort": None})
    except Exception as e:  # 網站改版或暫時連不上；結束碼 1 讓這一步顯示失敗並開 Issue，舊檔不動
        sys.exit(f"fail  央行牌告利率資訊網抓取失敗，沿用舊資料：{e}")
    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    fresh = parse(resp)
    if len(fresh) < 10:
        sys.exit(f"fail  只解析出 {len(fresh)} 家，表格格式可能變了，沿用舊資料（原始回應在 {RAW}）")
    banks = {b["n"]: b for b in old["banks"]}
    for name, r in fresh.items():
        b = banks.setdefault(name, {"n": name, "k": "公股" if name in PUBLIC else "民營", "d": {}, "td": {}, "ts": {}})
        b["src"] = f"{BASE}/"
        if b.get("note", "").startswith("只有部分期別"):
            del b["note"]
        b["d"].update(r["d"])
        b["td"].update(r["td"])
        b["ts"].update(r["ts"])
    old["banks"] = list(banks.values())
    old["asof"] = f"{dt.date.today():%Y-%m-%d}"
    OUT.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok  更新 {len(fresh)} 家銀行，共 {len(banks)} 家")


if __name__ == "__main__":
    main()
