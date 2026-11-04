"""理專憲章第一條「有據」的機器閘門：網站上的股價與本益比，必須和證交所當天公告的一樣。

每日更新抓完 data/tw.json 後，另外向證交所網站抓「同一個資料日」的公告，逐檔比對：
  - 收盤價（個股與 ETF）：必須完全相同
  - 本益比、殖利率、淨值比（個股）：差距在 0.01 以內（四捨五入）
ETF 的殖利率是網站用近一年配息自己算的，不是證交所公告值，不比對。

結果寫到 data/crosscheck.json（公開，資料狀態頁與 validate_data.py 會讀）。
有任何一檔不符 → 結束碼 1；validate_data.py 會把它當成錯誤，當天不發佈，網站繼續用上一份資料。
抓不到證交所網站時只記錄「這次沒有比對」，不擋發佈（不能因為對方網站掛掉就讓網站停更）。
用法：python scripts/crosscheck_twse.py
"""
import datetime as dt
import json
import sys
from pathlib import Path

from fetch_twse import num, site_bwibbu, site_day_all

ROOT = Path(__file__).resolve().parent.parent
TW = ROOT / "data" / "tw.json"
OUT = ROOT / "data" / "crosscheck.json"
TOL = {"pe": 0.01, "dy": 0.01, "pb": 0.01}
FIELDS = {"pe": "PEratio", "dy": "DividendYield", "pb": "PBratio"}
NAMES = {"p": "收盤價", "pe": "本益比", "dy": "殖利率", "pb": "淨值比"}


def compare(tw, closes, bw):
    """tw：data/tw.json 內容；closes：{代號: 證交所收盤列}；bw：{代號: 證交所本益比列}。回傳 (比對檔數, 不符清單)"""
    bad, n = [], 0
    for kind, rows in (("stock", tw["stocks"]), ("etf", tw["etfs"])):
        for s in rows:
            code = s["c"]
            ref = closes.get(code)
            if ref is None:
                bad.append({"c": code, "n": s["n"], "field": "p", "site": s["p"], "twse": None, "why": "證交所當天收盤表沒有這檔"})
                continue
            n += 1
            if num(ref.get("ClosingPrice")) != s["p"]:
                bad.append({"c": code, "n": s["n"], "field": "p", "site": s["p"], "twse": num(ref.get("ClosingPrice")), "why": "收盤價不同"})
            if kind == "etf":
                continue
            b = bw.get(code)
            if b is None:
                continue  # 證交所本益比表本來就不含部分股票（例如新上市），網站此時也是空值
            for k, tol in TOL.items():
                site, twse = s.get(k), num(b.get(FIELDS[k]))
                if site is None and twse is None:
                    continue
                if site is None or twse is None or abs(site - twse) > tol + 1e-9:
                    bad.append({"c": code, "n": s["n"], "field": k, "site": site, "twse": twse, "why": f"{NAMES[k]}差距超過 {tol}"})
    return n, bad


def main():
    tw = json.loads(TW.read_text(encoding="utf-8"))
    day = dt.date.fromisoformat(tw["asof"])
    out = {"asof": tw["asof"], "checked_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
           "source": ["https://www.twse.com.tw/exchangeReport/MI_INDEX", "https://www.twse.com.tw/exchangeReport/BWIBBU_d"],
           "tolerance": {"p": 0, **TOL}}
    try:
        closes = {r["Code"]: r for r in site_day_all(day)}
        bw = site_bwibbu(day)
        if not closes:
            raise RuntimeError(f"證交所網站沒有 {day} 的收盤表")
    except Exception as e:  # noqa: BLE001  對方網站連不上：記錄沒比對，不擋發佈
        out.update({"skipped": f"抓不到證交所網站：{e}", "checked": 0, "mismatches": []})
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"skip  {out['skipped']}")
        return
    n, bad = compare(tw, closes, bw)
    out.update({"checked": n, "mismatches": bad})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for b in bad[:20]:
        print(f"diff  {b['c']} {b['n']} {NAMES[b['field']]}：網站 {b['site']}，證交所 {b['twse']}（{b['why']}）")
    if bad:
        sys.exit(f"fail  {len(bad)} 項和證交所 {day} 的公告不符，這次不發佈")
    print(f"ok  {n} 檔和證交所 {day} 的公告一致")


if __name__ == "__main__":
    main()
