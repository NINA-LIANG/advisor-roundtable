"""下載知識庫原典全文並切成段落，供理專檢索佐證。

用法：python scripts/build_knowledge.py
輸出：knowledge/chunks/<source_id>.jsonl，每行一段 {"source", "advisors", "i", "text"}

只處理 sources.json 中 "ingest" 清單（公有領域與美國政府出版品）。
Project Gutenberg 的檔頭與檔尾授權聲明會被移除：依其條款，去掉這些聲明後的
公有領域文字可以自由使用，但不得再以 Project Gutenberg 名義散布。
"""

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
OUT = KNOWLEDGE / "chunks"
CHUNK_CHARS = 1500

START = re.compile(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.I)
END = re.compile(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG EBOOK", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "advisor-roundtable/0.1 (research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def gutenberg_text(book_id):
    raw = fetch(f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt")
    start, end = START.search(raw), END.search(raw)
    return raw[start.end() if start else 0 : end.start() if end else len(raw)]


def chunks(text):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 40]
    buf = ""
    for p in paras:
        p = re.sub(r"\s+", " ", p)
        if len(buf) + len(p) > CHUNK_CHARS and buf:
            yield buf
            buf = ""
        buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        yield buf


def main():
    sources = json.loads((KNOWLEDGE / "sources.json").read_text(encoding="utf-8"))["ingest"]
    OUT.mkdir(parents=True, exist_ok=True)
    for s in sources:
        if "gutenberg_id" not in s:
            # 政府網頁與 PDF 需另外轉文字，先跳過並提示
            print(f"skip  {s['id']}: 非 Gutenberg 來源，請手動轉成 knowledge/raw/{s['id']}.txt")
            raw_file = KNOWLEDGE / "raw" / f"{s['id']}.txt"
            if not raw_file.exists():
                continue
            text = raw_file.read_text(encoding="utf-8")
        else:
            try:
                text = gutenberg_text(s["gutenberg_id"])
            except Exception as e:
                print(f"fail  {s['id']}: {e}")
                continue
        n = 0
        with (OUT / f"{s['id']}.jsonl").open("w", encoding="utf-8") as f:
            for i, c in enumerate(chunks(text)):
                f.write(json.dumps({"source": s["id"], "advisors": s["advisors"], "i": i, "text": c}, ensure_ascii=False) + "\n")
                n = i + 1
        print(f"ok    {s['id']}: {n} chunks")


if __name__ == "__main__":
    main()
