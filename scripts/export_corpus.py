"""匯出論文實驗用的文件庫（CR-016；論文第三章 3-5、3-7）。

三個條件的「內容」必須完全相同，差別只在有沒有治理：
- 條件一（原始文件）：把原始檔案原樣複製出來，但拿掉治理加上去的東西（每條的 code 代號），
  也不放 knowledge/governance/。之後由實驗程式依固定字數切段，段落只以「檔名＋序號」識別。
- 條件二、三（治理後）：每個知識單元一行（units.jsonl），段落文字前面加上詮釋資料標頭；
  條件二不依權限過濾，條件三在檢索前用 scripts/kb_gate.py 的 allowed_units() 過濾、回答後過閘門。
研究者電腦上的受限文件（kb-private/*.json）兩邊都會放進去，不進 git。

用法：python scripts/export_corpus.py --out 某資料夾
  產出 某資料夾/condition1/…、某資料夾/condition23/units.jsonl、某資料夾/manifest.json（每個檔案的 SHA-256 與 git 版本）
凍結文件庫那天跑一次，把 manifest.json 一起事先登錄；之後網站再改，也不影響已凍結的這一份。
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog  # noqa: E402

ROOT = build_catalog.ROOT
# 表 3-1 的原始檔案（條件一）。教學網頁原稿裡的程式碼不算文件，所以憲章用網頁原稿、其餘用資料檔
RAW = ["web/charter.template.html", "docs/變更紀錄.md", "docs/變更分級與柱子地圖.md", "docs/憲章版本/*.md",
       "knowledge/corrections.zh.json", "knowledge/sources.json", "knowledge/insider.zh.json", "knowledge/basics.zh.json",
       "knowledge/advisors.zh.json", "knowledge/concepts.zh.json", "knowledge/bookshelf.zh.json"]


def strip_codes(x):
    if isinstance(x, dict):
        return {k: strip_codes(v) for k, v in x.items() if k != "code"}
    if isinstance(x, list):
        return [strip_codes(v) for v in x]
    return x


def header(u):
    src = u["source"] if isinstance(u["source"], str) else "；".join(f"{a} {b}" for a, b in u["source"])
    ver = f"{u['version']} {u['status']}".strip()
    return (f"[代號 {u['code']}｜類別 {u['category']}｜標題 {u['title']}｜出處 {src}｜資料日期 {u['date']}｜"
            f"版本與狀態 {ver}｜適用角色 {'、'.join(u['roles'])}｜敏感等級 {u['sensitivity']}]")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    out = Path(ap.parse_args().out)
    shutil.rmtree(out, ignore_errors=True)
    c1, c23 = out / "condition1", out / "condition23"
    c1.mkdir(parents=True)
    c23.mkdir(parents=True)
    for pat in RAW:
        for p in sorted(ROOT.glob(pat)):
            dest = c1 / p.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if p.suffix == ".json":
                dest.write_text(json.dumps(strip_codes(json.loads(p.read_text(encoding="utf-8"))), ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
            else:
                shutil.copy2(p, dest)
    priv = build_catalog.private_units()
    for u in priv:  # 受限文件在條件一是沒有詮釋資料的純文字檔
        d = c1 / "kb-private" / f"{u['code']}.md"
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_text(f"{u['title']}\n\n{u['text']}\n", encoding="utf-8")
    units = build_catalog.catalog()["units"] + priv
    with (c23 / "units.jsonl").open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(dict(u, indexed_text=header(u) + "\n" + u["text"]), ensure_ascii=False) + "\n")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    files = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}
    manifest = {"git_commit": commit, "units": len(units), "restricted_units": len(priv), "files": files}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok  {out}：條件一 {sum(1 for k in files if k.startswith('condition1'))} 個檔案；條件二、三 {len(units)} 個單元（受限 {len(priv)}）")


if __name__ == "__main__":
    main()
