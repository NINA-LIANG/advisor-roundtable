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

查詢方式照網頁「現行牌告利率查詢」：銀行類別 → 銀行名稱 → 利率項目 → 性質／存期／額度，最後送
Data/GetJsonFromArray。回應每列是「銀行 × 利率項目 × 存期 × 額度」的固定與機動利率，以金融機構代號
對回 rates.json 的銀行名稱。抓到的原始回應另存 data/raw/cbc_rates.json，對不上時可以拿來除錯。
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
TERM_KEYS = {"1", "3", "6", "9", "12", "24", "36"}  # rates.json 只收這幾個期別（月）
# 央行回應的銀行欄是「代號＋簡稱」（例如「004臺　銀」），以金融機構代號對回 rates.json 的名稱
CODES = {"004": "臺灣銀行", "005": "臺灣土地銀行", "006": "合作金庫", "007": "第一銀行", "008": "華南銀行",
         "009": "彰化銀行", "011": "上海銀行", "012": "台北富邦", "013": "國泰世華", "016": "高雄銀行",
         "017": "兆豐銀行", "018": "農業金庫", "048": "王道銀行", "050": "台灣企銀", "052": "渣打銀行",
         "053": "台中商銀", "081": "匯豐銀行", "101": "瑞興商銀", "102": "華泰商銀", "103": "新光銀行",
         "108": "陽信銀行", "118": "板信商銀", "147": "三信商銀", "700": "中華郵政", "803": "聯邦銀行",
         "805": "遠東銀行", "806": "元大銀行", "807": "永豐銀行", "808": "玉山銀行", "809": "凱基銀行",
         "810": "星展銀行", "812": "台新銀行", "816": "安泰銀行", "822": "中國信託", "823": "將來銀行",
         "824": "LINE Bank", "826": "樂天銀行"}
DEMAND = {"活期存款": "活期", "活期儲蓄存款": "活儲", "薪資轉帳活期儲蓄存款": "薪轉"}
PUBLIC = {"臺灣銀行", "臺灣土地銀行", "合作金庫", "第一銀行", "華南銀行", "彰化銀行", "兆豐銀行",
          "台灣企銀", "高雄銀行", "農業金庫"}


def post(path, body):
    raw = fetch(f"{BASE}/{path}", data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"})
    d = json.loads(raw.decode("utf-8"))
    # Data/GetJsonFromArray 回的是「JSON 字串裡再包一層 JSON」，要再解一次
    return json.loads(d) if isinstance(d, str) else d


def num(x):
    try:
        return float(re.sub(r"<[^>]+>|,", "", str(x)).strip())
    except ValueError:
        return None


def options(key, values):
    """模擬網頁上逐層點選：送出這一層選了什麼，回傳下一層的選項 {項目名稱: [選項]}。

    回應格式是 {"values": [{"Key": 下一層名稱, "Value": [...]}, {"Key": "利率項目代碼", ...}]}
    （鍵是大寫 Key/Value；2026-11 以前程式讀小寫 value，所以一直拿不到銀行名單）。
    """
    d = post("Range/GetJsonBirData", {"range": {"values": [{"key": key, "value": list(values)}]}})
    vals = d.get("values", []) if isinstance(d, dict) else []
    return {re.sub(r"[()（）\s]", "", str(v.get("Key", ""))): list(v.get("Value") or []) for v in vals if isinstance(v, dict)}


def query_range():
    """依網頁「現行牌告利率查詢」的順序：銀行類別 → 銀行名稱 → 利率項目 → 性質／存期／額度。"""
    names = options("銀行類別", CATEGORIES).get("銀行名稱", [])
    if not names:
        raise ValueError("央行網站沒有回傳銀行名單")
    lv = options("銀行名稱", names)
    items, codes = lv.get("利率項目", []), lv.get("利率項目代碼", [])
    # 只取新臺幣存款類（活期、活儲、薪轉、定存、定儲、郵局定儲金）；證券戶、無實體存單另有利率，不混進一般牌告
    keep = [i for i, x in enumerate(items) if re.search(r"存款|儲金", x) and not re.search(r"放款|外幣|外匯|證券|無實體", x)]
    if not keep:
        raise ValueError(f"利率項目裡沒有存款類：{items[:10]}")
    items, codes = [items[i] for i in keep], [codes[i] for i in keep if i < len(codes)]
    rest = options("利率項目", items)
    rng = [{"key": "銀行名稱", "value": names}, {"key": "利率項目", "value": items},
           {"key": "利率項目代碼", "value": codes}]
    for k in ("性質", "存期", "額度"):
        if rest.get(k):
            rng.append({"key": k, "value": rest[k]})
    print(f"note  銀行 {len(names)} 家、利率項目 {items}、" + "、".join(f"{x['key']} {len(x['value'])} 項" for x in rng[3:]))
    return {"values": rng}


def term(label):
    """「1月」「6月」「1年」「3年」→ 月數字串；活期的「--」回傳 None"""
    m = re.fullmatch(r"(\d+)\s*(月|個月|年)", label)
    if not m:
        return None
    return str(int(m.group(1)) * (12 if m.group(2) == "年" else 1))


def parse(resp):
    """央行回應：headerSet.Table1 是欄名（銀行名稱、利率項目、存期、額度、固定利率(%)、機動利率(%)），
    data 每列一個「銀行 × 項目 × 存期 × 額度」。只收額度「一般」、rates.json 用得到的期別。"""
    head = [h.get("data") for h in resp.get("headerSet", {}).get("Table1", [])]
    need = ("銀行名稱", "利率項目", "存期", "額度", "固定利率(%)", "機動利率(%)")
    if any(h not in head for h in need):
        raise ValueError(f"欄位對不上：{head}")
    ix = {h: head.index(h) for h in need}
    found, unknown = {}, set()
    for row in resp.get("data") or []:
        get = lambda h: re.sub(r"\s|\u3000", "", str(row[ix[h]]))
        if get("額度") != "一般":
            continue
        code = get("銀行名稱")[:3]
        name = CODES.get(code)
        if name is None:
            unknown.add(get("銀行名稱"))
            continue
        item, fixed, flt = get("利率項目"), num(get("固定利率(%)")), num(get("機動利率(%)"))
        b = found.setdefault(name, {"d": {}, "td": {}, "ts": {}})
        if item in DEMAND:
            if flt is not None:
                b["d"][DEMAND[item]] = flt
            continue
        part = {"定期存款": "td", "定期儲蓄存款": "ts"}.get(item)
        t = term(get("存期"))
        if part and t in TERM_KEYS and (fixed is not None or flt is not None):
            b[part][t] = [fixed, flt]
    if unknown:
        print(f"note  不在對照表、略過的銀行：{'、'.join(sorted(unknown))}", file=sys.stderr)
    return {k: v for k, v in found.items() if v["d"] or v["td"] or v["ts"]}


def main():
    old = json.loads(OUT.read_text(encoding="utf-8"))
    try:
        resp = post("Data/GetJsonFromArray", {"_range": query_range(), "BeginDate": None, "EndDate": None, "RateSort": None})
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
        b["src"] = f"{BASE}/Range/RangeSelect"
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
