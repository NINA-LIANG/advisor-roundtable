"""把知識庫與台股資料嵌入網頁模板，產生單一檔案的 web/index.html、web/sim.html 與 web/rates.html。

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
}
SHELL = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
         '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n</head>\n<body>\n{}\n</body>\n</html>\n')


def read(path):
    return path.read_text(encoding="utf-8")


def pages():
    tw = read(ROOT / "data" / "tw.json").strip()
    profiles = read(ROOT / "knowledge" / "advisors.zh.json").strip()
    insider = json.dumps(json.loads(read(ROOT / "knowledge" / "insider.zh.json")), ensure_ascii=False)
    src = read(WEB / "index.template.html")
    index = (src.replace("/*KB*/", read(WEB / "kb.js").strip())
                .replace("/*TW*/", tw)
                .replace("/*PROFILES*/", profiles)
                .replace("/*INSIDER*/", insider)
                .replace("__ASOF__", json.loads(tw)["asof"]))
    # 模擬倉共用理專圓桌的資料與六位理專的規則
    shared = src[src.index("// ---------- 台股資料"):src.index("const TABS=")]
    sim = (read(WEB / "sim.template.html").replace("/*SHARED*/", shared)
           .replace("/*TW*/", tw).replace("/*PROFILES*/", profiles))
    rates = read(WEB / "rates.template.html").replace("/*RATES*/", json.dumps(
        json.loads(read(ROOT / "data" / "rates.json")), ensure_ascii=False, separators=(",", ":")))
    return {"index.html": index, "sim.html": sim, "rates.html": rates}


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
            html = html.replace(f'href="{url}" target="_blank" rel="noopener"', f'href="{rel}"')
        (WEB / name).write_text(SHELL.format(html), encoding="utf-8")
        print(f"ok  web/{name}")


if __name__ == "__main__":
    main()
