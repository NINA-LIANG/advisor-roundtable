"""抓上市櫃公司最新一季財報（綜合損益表、資產負債表）與最新月營收，寫入 data/financials.json。

來源（公開資訊觀測站的彙總表，證交所／櫃買中心開放資料，免金鑰）：
- 上市綜合損益表：https://openapi.twse.com.tw/v1/opendata/t187ap06_L_{ci,basi,bd,fh,ins,mim}
- 上市資產負債表：https://openapi.twse.com.tw/v1/opendata/t187ap07_L_{同上}
- 上市月營收：https://openapi.twse.com.tw/v1/opendata/t187ap05_L
- 上櫃同上：https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_*、mopsfin_t187ap07_O_*、mopsfin_t187ap05_O
  （ci 一般業、basi 銀行、bd 證券、fh 金控、ins 保險、mim 異業；各業欄位名稱不同，下面 PICK 逐一列出）
財報是「今年第 1 季到最新一季」的累計數，原始單位千元，這裡換成億元。
用法：python scripts/fetch_financials.py             （線上抓）
      python scripts/fetch_financials.py --raw DIR   （用已下載的 <表名>.json，例如 t187ap06_L_ci.json）
任何一張表抓不到就略過；全部都抓不到才沿用舊檔。
"""
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

from net import fetch

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "financials.json"
TWSE = "https://openapi.twse.com.tw/v1/opendata/"
TPEX = "https://www.tpex.org.tw/openapi/v1/mopsfin_"
KINDS = ("ci", "basi", "bd", "fh", "ins", "mim")
TABLES = ([(TWSE, f"t187ap06_L_{k}", "is") for k in KINDS] + [(TWSE, f"t187ap07_L_{k}", "bs") for k in KINDS]
          + [(TWSE, "t187ap05_L", "rev")]
          + [(TPEX, f"t187ap06_O_{k}", "is") for k in KINDS] + [(TPEX, f"t187ap07_O_{k}", "bs") for k in KINDS]
          + [(TPEX, "t187ap05_O", "rev")])

# 每個欄位依序試這些名稱，取第一個有值的（各業別、上市櫃的表頭不一樣）
PICK = {
    "code": ("公司代號", "SecuritiesCompanyCode", "CompanyCode"),
    "rev": ("營業收入", "淨收益", "收益", "收入", "營業收入合計"),
    "gp": ("營業毛利（毛損）淨額", "營業毛利（毛損）"),
    "op": ("營業利益（損失）",),
    "pre": ("稅前淨利（淨損）", "繼續營業單位稅前淨利（淨損）", "繼續營業單位稅前損益", "繼續營業單位稅前純益（純損）"),
    "net": ("本期淨利（淨損）", "本期稅後淨利（淨損）"),
    "np": ("淨利（淨損）歸屬於母公司業主", "淨利（損）歸屬於母公司業主"),
    "eps": ("基本每股盈餘（元）",),
    "assets": ("資產總計", "資產總額"),
    "liab": ("負債總計", "負債總額"),
    "eq": ("權益總計", "權益總額"),
    "eqp": ("歸屬於母公司業主之權益合計",),
    "ca": ("流動資產",),
    "cl": ("流動負債",),
    "bvps": ("每股參考淨值",),
    "year": ("年度",),
    "q": ("季別",),
    "ym": ("資料年月",),
    "m": ("營業收入-當月營收",),
    "mom": ("營業收入-上月比較增減(%)",),
    "yoy": ("營業收入-去年同月增減(%)",),
    "ytd": ("累計營業收入-當月累計營收",),
    "ytdyoy": ("累計營業收入-前期比較增減(%)",),
}
IS_COLS = ("rev", "gp", "op", "pre", "net", "np", "eps")
BS_COLS = ("assets", "liab", "eq", "eqp", "ca", "cl", "bvps")
COLS = IS_COLS + BS_COLS
PER_SHARE = {"eps", "bvps"}
REV_COLS = ("ym", "m", "mom", "yoy", "ytd", "ytdyoy")


def num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def pick(row, field):
    for k in PICK[field]:
        v = row.get(k)
        if v not in (None, "", "-"):
            return v
    return None


def yi(v, field):
    """千元 → 億元；每股數字維持元"""
    v = num(v)
    if v is None:
        return None
    return round(v, 2) if field in PER_SHARE else round(v / 1e5, 2)


def parse(tables):
    """tables: [(表名, 種類 is/bs/rev, 資料列)] → (fin, mrev, 季別, 月份)"""
    fin, mrev, quarters, months = {}, {}, Counter(), Counter()
    for _, kind, rows in tables:
        for r in rows:
            code = str(pick(r, "code") or "").strip()
            if not code:
                continue
            if kind == "rev":
                ym = str(pick(r, "ym") or "")
                if len(ym) < 4:
                    continue
                y, m = int(ym[:-2]) + 1911, int(ym[-2:])
                months[f"{y}-{m:02d}"] += 1
                pct = lambda f: None if num(pick(r, f)) is None else round(num(pick(r, f)), 1)
                mrev[code] = [f"{y}-{m:02d}", yi(pick(r, "m"), "m"), pct("mom"), pct("yoy"), yi(pick(r, "ytd"), "ytd"), pct("ytdyoy")]
                continue
            y, q = num(pick(r, "year")), num(pick(r, "q"))
            if y and q:
                quarters[(int(y) + 1911, int(q))] += 1
            row = fin.setdefault(code, [None] * len(COLS))
            for f in IS_COLS if kind == "is" else BS_COLS:
                v = yi(pick(r, f), f)
                if v is not None:
                    row[COLS.index(f)] = v
    q = quarters.most_common(1)[0][0] if quarters else None
    m = months.most_common(1)[0][0] if months else None
    return fin, mrev, q, m


def main():
    raw = Path(sys.argv[2]) if len(sys.argv) == 3 and sys.argv[1] == "--raw" else None
    tables, missing = [], []
    for base, name, kind in TABLES:
        try:
            rows = json.loads((raw / f"{name}.json").read_text(encoding="utf-8")) if raw else json.loads(fetch(base + name))
        except Exception as e:  # 單一張表失敗就略過，其他照常
            missing.append(f"{name}（{e}）")
            continue
        if isinstance(rows, list):
            tables.append((name, kind, rows))
    fin, mrev, q, m = parse(tables)
    for x in missing:
        print(f"skip  {x}", file=sys.stderr)
    if len(fin) < 500:
        print(f"財報只有 {len(fin)} 家，沿用舊檔", file=sys.stderr)
        sys.exit(1)
    out = {"asof": dt.date.today().isoformat(), "quarter": f"{q[0]} Q{q[1]}" if q else "", "rev_month": m or "",
           "cols": list(COLS), "rev_cols": list(REV_COLS), "unit": "億元（EPS、每股淨值為元）",
           "fin": fin, "mrev": mrev, "missing": [x.split("（")[0] for x in missing]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"ok  {OUT}：財報 {len(fin)} 家（{out['quarter']} 累計）、月營收 {len(mrev)} 家（{m}）")


if __name__ == "__main__":
    main()
