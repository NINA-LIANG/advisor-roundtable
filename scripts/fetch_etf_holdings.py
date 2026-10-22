"""抓每檔台股 ETF 的持股明細與產業分布（MoneyDJ 持股狀況頁），寫入 data/etf_holdings.json。

每檔 ETF 一頁：https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid=<代號>.TW
國內股票型 ETF 每季公布全部持股、每月公布前五大；海外與債券 ETF 揭露較少。
用法：python scripts/fetch_etf_holdings.py            （依 data/universe.json 的 ETF 清單全部抓，一週內抓過就跳過；--force 強制）
      python scripts/fetch_etf_holdings.py --html DIR （解析已下載的 <代號>.html）
任何一檔失敗就保留舊資料，不會整份清空。
"""
import html as H
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "etf_holdings.json"
MAXH = 100
URL = "https://www.moneydj.com/ETF/X/Basic/Basic0007a.xdjhtm?etfid={}.TW"


def text(s):
    return H.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def num(s):
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def parse(page):
    """回傳 {d: 說明, sd: 產業資料日, sec: [[產業, %]], hd: 持股資料日, h: [[名稱, %]]}"""
    out = {}
    m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', page) or \
        re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', page)
    if m:
        out["d"] = H.unescape(m.group(1)).strip()
    i = page.find("持股依產業")
    j = page.find("持股明細表格 Start")
    if i >= 0 and j > i:
        blk = page[i:j]
        d = re.search(r"資料日期：(\d{4}/\d\d/\d\d)", blk)
        out["sd"] = d.group(1) if d else ""
        out["sec"] = [[text(a), num(text(b))] for a, b in
                      re.findall(r'class="col02">(.*?)</td>.*?class="col04">(.*?)</td>', blk, re.S)]
        out["sec"].sort(key=lambda x: -(x[1] or 0))
    if j >= 0:
        blk = page[j:page.find("投資比例彙總表", j) if page.find("投資比例彙總表", j) > 0 else j + 200000]
        d = re.search(r"資料日期：(\d{4}/\d\d/\d\d)", blk)
        out["hd"] = d.group(1) if d else ""
        h = [[text(a).rstrip("*").strip(), num(text(b))] for a, b in
             re.findall(r'class="col05">(.*?)</td>.*?class="col07">(.*?)</td>', blk, re.S)]
        h.sort(key=lambda x: -(x[1] or 0))
        out["n"] = len(h)
        out["h"] = h[:MAXH]  # 海外 ETF 可能有上千檔，只留權重最高的
    return out


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"etfs": {}}
    etfs = old.get("etfs", {})
    full = False
    if len(sys.argv) == 3 and sys.argv[1] == "--html":
        for f in sorted(Path(sys.argv[2]).glob("*.html")):
            r = parse(f.read_text(encoding="utf-8"))
            if r.get("h") or r.get("sec"):
                etfs[f.stem] = r
    else:
        uni = json.loads((ROOT / "data" / "universe.json").read_text(encoding="utf-8"))
        # 槓桿反向與期貨型 ETF 持有的是期貨合約，沒有成分股
        codes = [e[0] for e in uni["etf"] if e[3] not in ("槓桿反向", "商品期貨")]
        last = old.get("asof", "")
        fresh = last and (time.time() - time.mktime(time.strptime(last, "%Y-%m-%d"))) < 6 * 86400
        if fresh and "--force" not in sys.argv:
            codes = [c for c in codes if c not in etfs]  # 一週內抓過的不重抓，只補缺的
        else:
            full = True
        if not codes:
            print(f"etf_holdings: {last} 已抓過，沒有缺的")
            return
        ok = 0
        for code in codes:
            try:
                req = urllib.request.Request(URL.format(code), headers={"User-Agent": "Mozilla/5.0"})
                page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
                r = parse(page)
                if r.get("h") or r.get("sec"):
                    etfs[code] = r
                    ok += 1
            except Exception as e:  # noqa: BLE001
                print(f"warn {code}: {e}")
            time.sleep(1.5)
        print(f"ok {ok} 檔")
    old["etfs"] = etfs
    if full or "asof" not in old:  # 只有整批重抓才更新日期，避免每天補幾檔就延後全面更新
        old["asof"] = time.strftime("%Y-%m-%d")
    old["src"] = "MoneyDJ ETF 持股狀況（投信公告）"
    OUT.write_text(json.dumps(old, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"etf_holdings: {len(etfs)} 檔")


if __name__ == "__main__":
    main()
