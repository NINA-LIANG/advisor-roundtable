"""把知識庫與台股資料嵌入網頁模板，產生單一檔案的 web/*.html（每頁都套上共用導覽列與頁尾）。

用法：python scripts/fetch_twse.py && python scripts/fetch_rates.py && python scripts/build_site.py
      python scripts/build_site.py --bare OUTDIR   產生不含 <html>/<head> 外殼的版本（給 Claude Artifact 發佈）
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

from validate_data import DATASETS, validate

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
SITE_URL = "https://nina-liang.github.io/advisor-roundtable/"
# 資料狀態頁只在 GitHub Pages 上（要讀每日更新的結果），Artifact 版連到那裡
ARTIFACT_URLS[SITE_URL + "status.html"] = "status.html"
# 論文實驗頁也只在 GitHub Pages 上（要送資料到 DataPipe）
ARTIFACT_URLS[SITE_URL + "study.html"] = "study.html"
PAGE_URL = {rel: url for url, rel in ARTIFACT_URLS.items()}
# 全站導覽：依使用者要做的事分三組
NAV = [("學", [("learn.html", "入門教室"), ("news.html", "人氣小報")]),
       ("查", [("market.html", "台股全覽"), ("dividend.html", "除權息"), ("rates.html", "存款利率")]),
       ("做", [("sim.html", "百萬模擬倉"), ("lab.html", "理專考場"), ("study.html", "參加研究")])]  # 理專圓桌（首頁）就是左邊的站名
# 左側目錄：分組標題、副標，每項的圖示（數字由 pages() 依資料算）
DRAWER = [("學", "打好基本功", [("learn.html", "🌱", "入門教室"), ("news.html", "📰", "人氣小報")]),
          ("查", "看懂市場資料", [("market.html", "📇", "台股全覽"), ("dividend.html", "💰", "除權息行事曆"),
                             ("rates.html", "🏦", "存款利率")]),
          ("做", "練習自己判斷", [("index.html", "✨", "理專圓桌"), ("sim.html", "🐷", "百萬模擬倉"),
                             ("lab.html", "🧪", "理專考場"), ("study.html", "🎓", "參加研究")]),
          ("站", "認識這個網站", [("about.html", "📖", "關於本站"), ("status.html", "🩺", "資料狀態")])]
DISCLAIMER = ("示範與教育用途，非投資建議。資料來自證交所、櫃買中心等公開資料（盤後快照，非即時）。"
              "理專皆為虛構角色，選股是固定規則的計算結果，不保證準確。本站不收費、不收廣告、不提供個人化推介；"
              "依證券投資信託及顧問法，提供有價證券推介建議並收取報酬須取得投顧執照。實際投資請自行判斷並諮詢合格專業人員。")
SITE_NAME = "理專圓桌"
# 每頁的分頁標題與搜尋／分享摘要（只用在 GitHub Pages 版）
META = {
    "index.html": ("理專圓桌｜六位 AI 理專的台股 ETF 推薦",
                   "六位方法不同的 AI 理專，每個交易日依證交所收盤資料從台股與 ETF 挑標的、互相質疑，理由與數字全部攤開。示範與教育用途，非投資建議。"),
    "sim.html": ("百萬模擬倉｜理專圓桌", "用 100 萬虛擬資金跟著六位 AI 理專買賣台股，看哪一套方法績效好、回檔多深。資料存在你的瀏覽器，不需註冊。"),
    "rates.html": ("存款利率比較｜理專圓桌", "台灣各銀行活存、定存牌告利率一次比較，依中央銀行資料每個交易日更新，附存款保險與試算。"),
    "news.html": ("投資人氣小報｜理專圓桌", "台股定期定額排行、ETF 受益人數與熱門話題的每月整理，看大家在買什麼、為什麼。"),
    "learn.html": ("投資入門教室｜理專圓桌", "十分鐘看懂殖利率、本益比、內扣費用、除權息與稅費，附白話名詞表，給剛開始投資台股與 ETF 的人。"),
    "market.html": ("台股全覽｜理專圓桌", "上市、上櫃全部股票與 ETF 一覽，可依產業、殖利率、本益比篩選，並查看 ETF 持股與產業分布。"),
    "dividend.html": ("除權息行事曆｜理專圓桌", "台股與 ETF 除權息預告、結果與殖利率，依證交所、櫃買中心資料每個交易日更新。"),
    "about.html": ("關於本站｜理專圓桌", "理專圓桌是探討「人在迴圈中／迴圈上」的研究原型：六位虛構 AI 理專的規則、資料來源、隱私說明與限制。"),
    "lab.html": ("理專考場｜理專圓桌", "參考 AIOpsLab 的故障注入評測：在台股資料裡埋入 48 種錯誤，看 AI 理專與看門狗能不能抓出來。"),
    "status.html": ("資料狀態｜理專圓桌", "理專圓桌每份資料的日期、筆數與更新狀態，以及公開資料下載與歷史快照。"),
    "404.html": ("找不到這一頁｜理專圓桌", "這個網址沒有內容，從這裡回到理專圓桌的各個頁面。"),
    "study.html": ("理專圓桌研究｜投資判斷實驗", "論文使用者實驗：用歷史股市資料判斷要不要買，研究人如何使用 AI 理專的建議。"),
}
# 不放進 sitemap、不給搜尋引擎收錄的頁面；實驗頁只透過研究者發的連結進入
UNLISTED = ("404.html", "study.html")
# 實驗頁把作答資料送到 DataPipe（免費的線上實驗資料收集服務，資料存到研究者的 Google 雲端硬碟）
DATAPIPE = "https://pipe.jspsych.org"
EXP = ROOT / "knowledge" / "experiment"
# 選用：GoatCounter 流量分析（不設 cookie）。在 repo 的 Actions 變數設定 GOATCOUNTER_CODE 才會啟用
GOATCOUNTER = os.environ.get("GOATCOUNTER_CODE", "").strip()
SHELL = '<!doctype html>\n<html lang="zh-Hant">\n<head>\n{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n'



def active_etfs():
    """模擬倉的主動型 ETF 練習區：全部主動式 ETF 的收盤（universe.json）＋前三大持股（etf_holdings.json）"""
    uni = json.loads(read(ROOT / "data" / "universe.json"))
    hold = json.loads(read(ROOT / "data" / "etf_holdings.json"))["etfs"]
    rows = []
    for c, n, mk, kind, close, chg, tv in uni["etf"]:
        if kind != "主動式" or not close:
            continue
        prev = close - chg
        h = hold.get(c, {})
        rows.append({"c": c, "n": n, "mk": mk, "p": close, "chg": round(chg / prev * 100, 2) if prev else 0.0,
                     "tv": tv, "h": h.get("h", [])[:3], "hd": h.get("hd", ""), "nh": h.get("n", 0)})
    rows.sort(key=lambda r: -r["tv"])
    return json.dumps({"asof": uni["asof"], "list": rows}, ensure_ascii=False, separators=(",", ":"))

def head(name, top):
    """GitHub Pages 版的 <head>：基本設定、搜尋與分享資訊、圖示、安全設定，再接模板自己的字型與樣式"""
    title, desc = META[name]
    url = SITE_URL + ("" if name == "index.html" else name)
    gc = " https://gc.zgo.at" if GOATCOUNTER else ""
    gcd = f" https://{GOATCOUNTER}.goatcounter.com" if GOATCOUNTER else ""
    csp = (f"default-src 'self'; script-src 'self' 'unsafe-inline'{gc}"
           "; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com"
           f"; img-src 'self' data:{gcd}; connect-src 'self'{gcd}{' ' + DATAPIPE if name == 'study.html' else ''}"
           f"; base-uri 'self' {SITE_URL}; form-action 'none'; object-src 'none'")
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL, "inLanguage": "zh-Hant",
          "description": META["index.html"][1],
          "author": {"@type": "Person", "name": "梁瑜庭", "url": "https://github.com/NINA-LIANG"}}
    rows = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f'<meta http-equiv="Content-Security-Policy" content="{csp}">',
        '<meta name="referrer" content="strict-origin-when-cross-origin">',
        f"<title>{title}</title>",
        f'<meta name="description" content="{desc}">',
        f'<link rel="canonical" href="{url}">' if name not in UNLISTED else '<meta name="robots" content="noindex">',
        f'<base href="{SITE_URL}">' if name == "404.html" else "",
        '<link rel="icon" href="favicon.svg" type="image/svg+xml">',
        '<link rel="icon" href="favicon-32.png" sizes="32x32" type="image/png">',
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">',
        '<meta name="theme-color" content="#fff7ef">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{desc}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{SITE_URL}og.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{SITE_NAME}：六位 AI 理專的台股 ETF 推薦">',
        '<meta property="og:locale" content="zh_TW">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if name == "index.html" else "",
        (f'<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>'
         if GOATCOUNTER else ""),
        # 模板開頭的 <title>、Artifact 專用 meta 換掉，其餘字型與樣式照搬
        re.sub(r"<title>.*?</title>\n?|<meta name=\"claude:[^>]*>\n?", "", top),
    ]
    return "\n".join(r for r in rows if r)


def sitemap(names, asof):
    urls = "".join(f"<url><loc>{SITE_URL}{'' if n == 'index.html' else n}</loc>"
                   f"{f'<lastmod>{asof[n]}</lastmod>' if asof.get(n) else ''}</url>\n" for n in names)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}</urlset>\n")


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
    badge = f'<span class="asofb" data-asof="{asof}" title="資料日期 {asof}">資料 {asof[5:]}</span>' if asof else ""
    nav = (f"<style>{css}</style>\n<a class=\"skip\" href=\"#main\">跳到主要內容</a>\n{drawer(cur, counts)}\n<nav class=\"sitenav\" aria-label=\"網站導覽\">"
           '<button class="navbtn" type="button" aria-controls="sitedrawer" aria-expanded="false" aria-label="打開目錄">☰</button>'
           f'<a class="brand" href="{PAGE_URL["index.html"]}" target="_blank" rel="noopener"{' aria-current="page"' if cur == "index.html" else ""}>✨ 理專圓桌</a>'
           f'{groups}{link("about.html", "關於本站", cur)}{badge}</nav>')
    gl = {"terms": basics["terms"], "url": PAGE_URL["learn.html"]}
    foot = (f'<footer class="sitefoot">{DISCLAIMER} <a href="{PAGE_URL["about.html"]}" target="_blank" rel="noopener">關於本站與資料來源</a></footer>\n'
            f"<script>window.__GL__={json.dumps(gl, ensure_ascii=False, separators=(',', ':'))};\n{read(WEB / '_shared.js')}</script>")
    assert "<!--SITE-NAV-->" in html and "<!--SITE-FOOT-->" in html, cur
    # 主內容地標：導覽列之後到外層容器結束（模板第一個頂層 </div>）
    i = html.index("<!--SITE-NAV-->")
    j = html.index("\n</div>", i)
    html = html[:i] + "<!--SITE-NAV-->\n<main id=\"main\" tabindex=\"-1\">" + html[i + 15:j] + "\n</main>" + html[j:]
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
           .replace("/*TW*/", tw).replace("/*PROFILES*/", profiles).replace("/*SHELF*/", shelf)
           .replace("/*ACTIVE*/", active_etfs()))
    rates = read(WEB / "rates.template.html").replace("/*RATES*/", json.dumps(
        json.loads(read(ROOT / "data" / "rates.json")), ensure_ascii=False, separators=(",", ":")))
    news = read(WEB / "news.template.html").replace("/*NEWS*/", json.dumps(
        json.loads(read(ROOT / "data" / "popular.json")), ensure_ascii=False, separators=(",", ":")))
    learn = read(WEB / "learn.template.html").replace("/*LEARN*/", json.dumps(
        json.loads(read(ROOT / "knowledge" / "basics.zh.json")), ensure_ascii=False, separators=(",", ":")))
    compact = lambda name: json.dumps(json.loads(read(ROOT / "data" / name)), ensure_ascii=False, separators=(",", ":"))
    market = (read(WEB / "market.template.html").replace("/*UNIVERSE*/", compact("universe.json"))
              .replace("/*HOLDINGS*/", compact("etf_holdings.json")).replace("/*FIN*/", compact("financials.json")))
    # 除權息頁只需要每檔的收盤、產業／類型、股或 ETF、市場
    uni = json.loads(read(ROOT / "data" / "universe.json"))
    px = {r[0]: [r[4], r[3], "s", r[2]] for r in uni["stock"]}
    px.update({r[0]: [r[4], r[3], "e", r[2]] for r in uni["etf"]})
    dividend = (read(WEB / "dividend.template.html").replace("/*DIVIDENDS*/", compact("dividends.json"))
                .replace("/*PX*/", json.dumps(px, ensure_ascii=False, separators=(",", ":"))))
    # 關於本站：理專的名字、樣式從首頁的 ADVISORS 抓
    adv = [dict(zip(("key", "name", "emoji", "tape", "style"), m)) for m in re.findall(
        r'\{key:"(\w+)",name:"([^"]+)",emoji:"([^"]+)",tape:"([^"]+)".*?style:"([^"]+)"', src)]
    # 理專考場：跟模擬倉一樣共用首頁的資料與六位理專
    lab = (read(WEB / "lab.template.html").replace("/*SHARED*/", shared)
           .replace("/*TW*/", tw).replace("/*PROFILES*/", profiles).replace("/*SHELF*/", shelf))
    note = ("本站用 GoatCounter 計算瀏覽次數：不設 cookie、不追蹤個人，只記錄頁面、來源網站與裝置類型的總數。"
            if GOATCOUNTER else "本站目前沒有任何流量分析或追蹤程式。")
    about = (read(WEB / "about.template.html").replace("/*PROFILES*/", profiles).replace("<!--ANALYTICS-NOTE-->", note)
             .replace("/*ADVISORS*/", json.dumps(adv, ensure_ascii=False)))
    basics = json.loads(read(ROOT / "knowledge" / "basics.zh.json"))
    st = status()
    status_page = read(WEB / "status.template.html").replace("/*STATUS*/", json.dumps(st, ensure_ascii=False, separators=(",", ":")))
    asof = {"index.html": json.loads(tw)["asof"], "sim.html": json.loads(tw)["asof"],
            "rates.html": json.loads(read(ROOT / "data" / "rates.json")).get("asof", ""),
            "news.html": "",
            "learn.html": "", "market.html": uni["asof"],
            "dividend.html": json.loads(read(ROOT / "data" / "dividends.json"))["asof"], "about.html": "", "lab.html": json.loads(tw)["asof"],
            "status.html": "", "404.html": "", "study.html": ""}
    out = {"study.html": study(), "index.html": index, "sim.html": sim, "rates.html": rates, "news.html": news, "learn.html": learn,
           "market.html": market, "dividend.html": dividend, "about.html": about, "lab.html": lab,
           "status.html": status_page, "404.html": read(WEB / "404.template.html")}
    div = json.loads(read(ROOT / "data" / "dividends.json"))
    counts = {"learn.html": len(basics["terms"]), "news.html": "月刊",
              "market.html": f'{len(uni["stock"]) + len(uni["etf"]):,}',
              "dividend.html": sum(1 for e in div["up"] if e[0] >= div["asof"]),
              "rates.html": len(json.loads(read(ROOT / "data" / "rates.json"))["banks"]), "index.html": 6, "sim.html": "100萬", "lab.html": "48 題", "study.html": "30 分鐘",
              "status.html": {"ok": "✅", "warn": "⚠️", "error": "❌"}[worst(st)]}
    # 實驗頁不套導覽列與頁尾：受試者不該在作答中跑去看理專圓桌的其他頁面
    return {k: v if k == "study.html" else chrome(v, k, asof[k], basics, counts) for k, v in out.items()}, asof


def study():
    """論文實驗頁：嵌入凍結題庫（正式題不含答案）、問卷與研究設定；題庫還沒產生時 ITEMS 是 null"""
    items_path = EXP / "items.v1.json"
    items = read(items_path) if items_path.exists() else "null"
    cfg = json.loads(read(EXP / "config.json"))["study"]
    manifest = json.loads(read(EXP / "manifest.json")) if (EXP / "manifest.json").exists() else {}
    data = {"config": cfg, "surveys": json.loads(read(EXP / "surveys.zh.json")), "items_sha": manifest.get("items.v1.json", "")}
    return (read(WEB / "study.template.html").replace("/*ITEMS*/", json.dumps(json.loads(items), ensure_ascii=False, separators=(",", ":")))
            .replace("/*STUDY*/", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))


def status():
    """每日更新時由 validate_data.py --status 寫出（含各抓取步驟成敗）；本機建置沒有這個檔就當場檢查"""
    path = ROOT / "data" / "status.json"
    return json.loads(read(path)) if path.exists() else validate()[2]


def worst(st):
    states = {d["state"] for d in st["datasets"]}
    return "error" if "error" in states or not st["ok"] else "warn" if "warn" in states else "ok"


def publish_data():
    """把網頁用到的資料也放上 Pages（web/data/），當成公開的唯讀 API；不進 git，每次建置重新複製"""
    dest = WEB / "data"
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir()
    for _, fname, *_ in DATASETS:
        shutil.copy2(ROOT / "data" / fname, dest / fname)
    (dest / "status.json").write_text(json.dumps(status(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok  web/data/（{len(DATASETS) + 1} 個 JSON）")


def main():
    out, asof = pages()
    if len(sys.argv) == 3 and sys.argv[1] == "--bare":
        dest = Path(sys.argv[2])
        for name, html in out.items():
            if name in ("404.html", "status.html", "study.html"):
                continue
            (dest / name).write_text(html, encoding="utf-8")
            print(f"ok  {dest / name}")
        return
    for name, html in out.items():
        for url, rel in ARTIFACT_URLS.items():
            html = html.replace(f'href="{url}" target="_blank" rel="noopener"', f'href="{rel}"').replace(url, rel)
        # 模板開頭到第一個 </style> 是字型與樣式，搬進 <head>
        k = html.index("</style>") + len("</style>")
        (WEB / name).write_text(SHELL.format(head=head(name, html[:k]), body=html[k:].lstrip("\n")), encoding="utf-8")
        print(f"ok  web/{name}")
    pub = [n for n in out if n not in UNLISTED]
    (WEB / "sitemap.xml").write_text(sitemap(pub, asof), encoding="utf-8")
    (WEB / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    print("ok  web/sitemap.xml, web/robots.txt")
    publish_data()
    # 實驗結束時的揭曉頁會讀這份（真實股票、日期與答案）；放在網站上而不是嵌進實驗頁，作答中看原始碼也看不到
    key = EXP / "key.v1.json"
    if key.exists():
        shutil.copy2(key, WEB / "study-key.json")
        print("ok  web/study-key.json")

if __name__ == "__main__":
    main()
