"""把知識庫與台股資料嵌入網頁模板，產生單一檔案的 web/*.html（每頁都套上共用導覽列與頁尾）。

用法：python scripts/fetch_twse.py && python scripts/fetch_rates.py && python scripts/build_site.py
      python scripts/build_site.py --bare OUTDIR   產生不含 <html>/<head> 外殼的版本（給 Claude Artifact 發佈）
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
# 各頁在 Claude Artifact 上的網址；部署到 GitHub Pages 時改成相對連結
ARTIFACT_URLS = {
    "https://claude.ai/artifact/Vj54WYe91o3L2eYVQMpLDT": "index.html",
    "https://claude.ai/artifact/M9a9miXiw6A48VKovkJVqb": "sim.html",
    "https://claude.ai/artifact/Bmc4PG8mYgvAV9iEik8PDz": "rates.html",
    "https://claude.ai/artifact/DMkJkY1CJP7BVhm61qV4Fx": "news.html",
    "https://claude.ai/artifact/RK74vfRrALWhutPXahWRtu": "learn.html",
    "https://claude.ai/artifact/Aj4eFHk9RZrjkuUmr7kRXb": "market.html",
    "https://claude.ai/artifact/UNwf3YLPP6nXTWfRGVrPaw": "dividend.html",
}
ABOUT_URL = "https://claude.ai/artifact/4yrjpspWAKxAFJ6zeodjpA"
ARTIFACT_URLS[ABOUT_URL] = "about.html"
LAB_URL = "https://claude.ai/artifact/2mfKRYx1SjgSHwN6w67Eu9"
ARTIFACT_URLS[LAB_URL] = "lab.html"
PAGE_URL = {rel: url for url, rel in ARTIFACT_URLS.items()}
# 全站導覽：依使用者要做的事分三組
NAV = [("學", [("learn.html", "入門教室"), ("news.html", "人氣小報")]),
       ("查", [("market.html", "台股全覽"), ("dividend.html", "除權息"), ("rates.html", "存款利率")]),
       ("做", [("index.html", "理專圓桌"), ("sim.html", "百萬模擬倉"), ("lab.html", "理專考場")])]
# 左側目錄：分組標題、副標，每項的圖示（數字由 pages() 依資料算）
DRAWER = [("學", "打好基本功", [("learn.html", "🌱", "入門教室"), ("news.html", "📰", "人氣小報")]),
          ("查", "看懂市場資料", [("market.html", "📇", "台股全覽"), ("dividend.html", "💰", "除權息行事曆"),
                             ("rates.html", "🏦", "存款利率")]),
          ("做", "練習自己判斷", [("index.html", "✨", "理專圓桌"), ("sim.html", "🐷", "百萬模擬倉"),
                             ("lab.html", "🧪", "理專考場")]),
          ("站", "認識這個網站", [("about.html", "📖", "關於本站")])]
DISCLAIMER = ("示範與教育用途，非投資建議。資料來自證交所、櫃買中心等公開資料（盤後快照，非即時）。"
              "理專皆為虛構角色，選股是固定規則的計算結果，不保證準確。本站不收費、不收廣告、不提供個人化推介；"
              "依證券投資信託及顧問法，提供有價證券推介建議並收取報酬須取得投顧執照。實際投資請自行判斷並諮詢合格專業人員。")
SHELL = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n</head>\n<body>\n{}\n</body>\n</html>\n')


def read(path):
    return path.read_text(encoding="utf-8")


def link(rel, text, cur):
    attr = ' aria-current="page"' if rel == cur else ""
    return f'<a href="{PAGE_URL[rel]}" target="_blank" rel="noopener"{attr}>{text}</a>'


def drawer(cur, counts):
    groups = []
    for g, sub, items in DRAWER:
        rows = "".join(
            f'<a href="{PAGE_URL[rel]}" target="_blank" rel="noopener"{" aria-current=\"page\"" if rel == cur else ""}>'
            f'<i aria-hidden="true">{ic}</i><span>{t}</span><small>{counts.get(rel, "")}</small></a>' for rel, ic, t in items)
        groups.append(f'<div class="dgrp"><h4>{g}<small>{sub}</small></h4>{rows}</div>')
    return ('<div class="drawer-bg" hidden></div>'
            '<aside class="drawer" id="sitedrawer" aria-label="網站目錄" hidden>'
            '<div class="dhead"><span class="dlogo" aria-hidden="true">✨</span><div><b>理專圓桌</b><small>Advisor Roundtable</small></div>'
            '<button class="dclose" type="button" aria-label="關閉目錄">✕</button></div>'
            f'{"".join(groups)}<p class="dnote">示範與教育用途，非投資建議</p></aside>')


def chrome(html, cur, asof, basics, counts):
    """把共用導覽列、樣式、頁尾聲明與名詞提示放進頁面"""
    css = read(WEB / "_shared.css")
    groups = "".join(f'<div class="grp"><span>{g}</span>{"".join(link(r, t, cur) for r, t in items)}</div>'
                     for g, items in NAV)
    badge = f'<span class="asofb" data-asof="{asof}">資料日期 {asof}</span>' if asof else ""
    nav = (f"<style>{css}</style>\n{drawer(cur, counts)}\n<nav class=\"sitenav\" aria-label=\"網站導覽\">"
           '<button class="navbtn" type="button" aria-controls="sitedrawer" aria-expanded="false" aria-label="打開目錄">☰</button>'
           f'<a class="brand" href="{PAGE_URL["index.html"]}" target="_blank" rel="noopener">✨ 理專圓桌</a>'
           f'{groups}{link("about.html", "關於本站", cur)}{badge}</nav>')
    gl = {"terms": basics["terms"], "url": PAGE_URL["learn.html"]}
    foot = (f'<footer class="sitefoot">{DISCLAIMER} <a href="{PAGE_URL["about.html"]}" target="_blank" rel="noopener">關於本站與資料來源</a></footer>\n'
            f"<script>window.__GL__={json.dumps(gl, ensure_ascii=False, separators=(',', ':'))};\n{read(WEB / '_shared.js')}</script>")
    assert "<!--SITE-NAV-->" in html and "<!--SITE-FOOT-->" in html, cur
    return html.replace("<!--SITE-NAV-->", nav, 1).replace("<!--SITE-FOOT-->", foot, 1)


def pages():
    tw = read(ROOT / "data" / "tw.json").strip()
    profiles = read(ROOT / "knowledge" / "advisors.zh.json").strip()
    shelf = json.dumps(json.loads(read(ROOT / "knowledge" / "bookshelf.zh.json")), ensure_ascii=False)
    insider = json.dumps(json.loads(read(ROOT / "knowledge" / "insider.zh.json")), ensure_ascii=False)
    src = read(WEB / "index.template.html")
    index = (src.replace("/*KB*/", read(WEB / "kb.js").strip())
                .replace("/*TW*/", tw)
                .replace("/*PROFILES*/", profiles)
                .replace("/*INSIDER*/", insider)
                .replace("/*SHELF*/", shelf)
                .replace("__ASOF__", json.loads(tw)["asof"]))
    # 模擬倉共用理專圓桌的資料與六位理專的規則
    shared = src[src.index("// ---------- 台股資料"):src.index("const TABS=")]
    sim = (read(WEB / "sim.template.html").replace("/*SHARED*/", shared)
           .replace("/*TW*/", tw).replace("/*PROFILES*/", profiles).replace("/*SHELF*/", shelf))
    rates = read(WEB / "rates.template.html").replace("/*RATES*/", json.dumps(
        json.loads(read(ROOT / "data" / "rates.json")), ensure_ascii=False, separators=(",", ":")))
    news = read(WEB / "news.template.html").replace("/*NEWS*/", json.dumps(
        json.loads(read(ROOT / "data" / "popular.json")), ensure_ascii=False, separators=(",", ":")))
    learn = read(WEB / "learn.template.html").replace("/*LEARN*/", json.dumps(
        json.loads(read(ROOT / "knowledge" / "basics.zh.json")), ensure_ascii=False, separators=(",", ":")))
    compact = lambda name: json.dumps(json.loads(read(ROOT / "data" / name)), ensure_ascii=False, separators=(",", ":"))
    market = (read(WEB / "market.template.html").replace("/*UNIVERSE*/", compact("universe.json"))
              .replace("/*HOLDINGS*/", compact("etf_holdings.json")))
    # 除權息頁只需要每檔的收盤、產業／類型、股或 ETF、市場
    uni = json.loads(read(ROOT / "data" / "universe.json"))
    px = {r[0]: [r[4], r[3], "s", r[2]] for r in uni["stock"]}
    px.update({r[0]: [r[4], r[3], "e", r[2]] for r in uni["etf"]})
    dividend = (read(WEB / "dividend.template.html").replace("/*DIVIDENDS*/", compact("dividends.json"))
                .replace("/*PX*/", json.dumps(px, ensure_ascii=False, separators=(",", ":"))))
    # 關於本站：理專的名字、樣式從首頁的 ADVISORS 抓
    import re
    adv = [dict(zip(("key", "name", "emoji", "tape", "style"), m)) for m in re.findall(
        r'\{key:"(\w+)",name:"([^"]+)",emoji:"([^"]+)",tape:"([^"]+)".*?style:"([^"]+)"', src)]
    # 理專考場：跟模擬倉一樣共用首頁的資料與六位理專
    lab = (read(WEB / "lab.template.html").replace("/*SHARED*/", shared)
           .replace("/*TW*/", tw).replace("/*PROFILES*/", profiles).replace("/*SHELF*/", shelf))
    about = (read(WEB / "about.template.html").replace("/*PROFILES*/", profiles)
             .replace("/*ADVISORS*/", json.dumps(adv, ensure_ascii=False)))
    basics = json.loads(read(ROOT / "knowledge" / "basics.zh.json"))
    asof = {"index.html": json.loads(tw)["asof"], "sim.html": json.loads(tw)["asof"],
            "rates.html": json.loads(read(ROOT / "data" / "rates.json")).get("asof", ""),
            "news.html": "",
            "learn.html": "", "market.html": uni["asof"],
            "dividend.html": json.loads(read(ROOT / "data" / "dividends.json"))["asof"], "about.html": "", "lab.html": json.loads(tw)["asof"]}
    out = {"index.html": index, "sim.html": sim, "rates.html": rates, "news.html": news, "learn.html": learn,
           "market.html": market, "dividend.html": dividend, "about.html": about, "lab.html": lab}
    div = json.loads(read(ROOT / "data" / "dividends.json"))
    counts = {"learn.html": len(basics["terms"]), "news.html": "月刊",
              "market.html": f'{len(uni["stock"]) + len(uni["etf"]):,}',
              "dividend.html": sum(1 for e in div["up"] if e[0] >= div["asof"]),
              "rates.html": len(json.loads(read(ROOT / "data" / "rates.json"))["banks"]), "index.html": 6, "sim.html": "100萬", "lab.html": "48 題"}
    return {k: chrome(v, k, asof[k], basics, counts) for k, v in out.items()}


def main():
    out = pages()
    if len(sys.argv) == 3 and sys.argv[1] == "--bare":
        dest = Path(sys.argv[2])
        for name, html in out.items():
            (dest / name).write_text(html, encoding="utf-8")
            print(f"ok  {dest / name}")
        return
    for name, html in out.items():
        for url, rel in ARTIFACT_URLS.items():
            html = html.replace(f'href="{url}" target="_blank" rel="noopener"', f'href="{rel}"').replace(url, rel)
        (WEB / name).write_text(SHELL.format(html), encoding="utf-8")
        print(f"ok  web/{name}")


if __name__ == "__main__":
    main()
