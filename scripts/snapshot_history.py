"""把當天的資料壓縮存成歷史快照，給之後的回測與「過去某天理專推薦什麼」使用。

用法：python scripts/snapshot_history.py DEST
輸出：DEST/YYYY/MM/YYYY-MM-DD/{tw,universe,dividends,rates}.json.gz 與 DEST/index.json（所有快照日期）
每日更新會把 DEST 放在獨立的 data-history 分支，主分支不會因為每天的舊資料越來越大。
日期以 tw.json 的資料日為準；同一天已經存過就不覆蓋。
"""

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ("tw", "universe", "dividends", "rates")


def snapshot(dest, root=ROOT):
    dest = Path(dest)
    asof = json.loads((root / "data" / "tw.json").read_text(encoding="utf-8"))["asof"]
    day = dest / asof[:4] / asof[5:7] / asof
    if day.exists():
        print(f"skip  {asof} 已經存過")
        return asof, False
    day.mkdir(parents=True)
    for name in FILES:
        src = root / "data" / f"{name}.json"
        if src.exists():
            # mtime=0 讓同樣內容壓出同樣的檔案，git 不會多記一次變動
            with gzip.GzipFile(day / f"{name}.json.gz", "wb", mtime=0) as f:
                f.write(src.read_bytes())
    index = sorted(p.name for p in dest.glob("*/*/*") if p.is_dir())
    (dest / "index.json").write_text(json.dumps({"dates": index, "files": list(FILES)}, ensure_ascii=False),
                                     encoding="utf-8")
    print(f"ok  {day.relative_to(dest)}，共 {len(index)} 天")
    return asof, True


if __name__ == "__main__":
    snapshot(sys.argv[1])
