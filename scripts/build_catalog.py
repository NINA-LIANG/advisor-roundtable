"""文件庫目錄（CR-016）：把網站的知識檔案與營運文件，整理成一條一條帶詮釋資料的「知識單元」。

對應論文第三章：表 3-1 文件庫三層、表 3-3 詮釋資料欄位與命名規則、表 3-4 角色與資料權限矩陣。
- 產出 knowledge/governance/catalog.json（公開；網站「文件庫」頁與出處驗證閘門都讀這一份）
- 研究者電腦上若有 kb-private/*.json（研究用虛構受限文件，不進 git），另外產出 kb-private/catalog_full.json
- 只整理、不改寫：每一單元的內文直接取自原始檔案；原始檔案沒有的欄位（例如概念卡的資料日期）
  依下方 FILE_DATE 補上，並在 date_note 註明來源

用法：python scripts/build_catalog.py            重建目錄
      python scripts/build_catalog.py --check    只檢查（代號唯一、格式、必要欄位、目錄與原始檔一致），CI 用
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_text import charter_sections, charter_version, md_tables  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
K = ROOT / "knowledge"
GOV = K / "governance"
OUT = GOV / "catalog.json"
PRIVATE = ROOT / "kb-private"
TAXO = json.loads((GOV / "taxonomy.json").read_text(encoding="utf-8"))
ROLES = json.loads((GOV / "roles.json").read_text(encoding="utf-8"))
CODE = re.compile(TAXO["pattern"])
SENS = {s["id"]: s for s in ROLES["sensitivity"]}
SELF = "本站自撰"
ADV = {"macro": ("MAC", "林思遠", "總體經濟循環"), "value": ("VAL", "王建明", "價值投資"), "tech": ("TEC", "陳怡君", "技術分析"),
       "mom": ("MOM", "周以恆", "動能趨勢"), "quant": ("QNT", "張雅雯", "均值回歸"), "div": ("DIV", "劉淑芬", "存股")}
# 原始檔案沒有記載資料日期者：取該檔案內容最後一次實質修改的日期（git 紀錄，CR-016 建立時查得）
FILE_DATE = {"concepts.zh.json": "2026-10-22", "bookshelf.zh.json": "2026-10-22", "advisors.zh.json": "2026-10-26",
             "變更分級與柱子地圖.md": "2026-11-05"}
CAT = {c["code"]: c for c in TAXO["categories"]}


def unit(code, title, text, file, *, source=SELF, date="", version="", status="現行", sens="public", partition=None, date_note=""):
    c = CAT[code[:3]]
    u = {"code": code, "layer": c["layer"], "category": c["name"], "title": title, "text": text.strip(), "source": source,
         "date": date, "version": version, "status": status, "roles": SENS[sens]["roles"], "sensitivity": SENS[sens]["name"],
         "file": file}
    if partition:
        u["partition"] = partition
    if date_note:
        u["date_note"] = date_note
    return u


def load(name):
    return json.loads((K / name).read_text(encoding="utf-8"))


def charter():
    out = []
    src = (ROOT / "web" / "charter.template.html").read_text(encoding="utf-8")
    ver, date = charter_version(src)
    for i, (t, b) in enumerate(charter_sections(src), 1):
        out.append(unit(f"CHT-V11-{i:02d}", f"理專憲章 {ver}：{t}", b, "web/charter.template.html", date=date, version=ver, status="現行"))
    # 舊版：docs/憲章版本/ 的全文存檔，研究設定為內部限定（表 3-4）
    for p in sorted((ROOT / "docs" / "憲章版本").glob("*.md")):
        md = p.read_text(encoding="utf-8")
        m = re.match(r"# 理專憲章 (v[\d.]+)（(\d{4}-\d{2}-\d{2})）", md)
        v, d = m.group(1), m.group(2)
        secs = re.split(r"^## ", md, flags=re.M)[1:]
        for i, s in enumerate(secs, 1):
            t, _, b = s.partition("\n")
            out.append(unit(f"CHT-V{v[1:].replace('.', '')}{'0' if '.' not in v else ''}-{i:02d}", f"理專憲章 {v}（舊版）：{t.strip()}", b,
                            f"docs/憲章版本/{p.name}", date=d, version=v, status="已被取代", sens="internal"))
    return out


def change_log():
    out = []
    text = (ROOT / "docs" / "變更紀錄.md").read_text(encoding="utf-8")
    for r in md_tables(text)[0]:
        n = r["編號"].split("-")[1]
        body = (f"變更單 {r['編號']}。提出日期：{r['提出日期']}；提出者：{r['提出者']}。變更內容：{r['變更內容']}。"
                f"憲章依據：{r['憲章依據']}。等級：{r['等級']}。決定者與決定：{r['決定者與決定']}。狀態：{r['狀態']}。對應 PR：{r['PR']}。")
        out.append(unit(f"GOV-CR-{n}", f"變更單 {r['編號']}", body, "docs/變更紀錄.md", date=r["提出日期"], status=r["狀態"], sens="internal"))
    grading = (ROOT / "docs" / "變更分級與柱子地圖.md").read_text(encoding="utf-8")
    pillars, levels, versions = md_tables(grading)
    ver = versions[-1]
    gstatus = "初稿" if "待核准" in ver.get("核准者", "") else "現行"
    d = FILE_DATE["變更分級與柱子地圖.md"]
    note = "原始檔案未記載修改日期，取 git 紀錄之最後修改日"
    for r in levels:
        lv = r["等級"].split()[0]
        body = f"變更等級 {r['等級']}。例子：{r['例子']}。流程：{r['流程']}。由誰核准：{r['由誰核准']}。機器檢查：{r['機器檢查']}。"
        out.append(unit(f"GOV-LVL-{lv}", f"變更等級 {r['等級']}", body, "docs/變更分級與柱子地圖.md", date=d, version=ver["版本"],
                        status=gstatus, sens="internal", date_note=note))
    for i, r in enumerate(pillars, 1):
        body = f"柱子：{r['柱子']}。主要檔案：{r['主要檔案']}。屬於：{r['屬於']}。"
        out.append(unit(f"GOV-PIL-{i:02d}", f"柱子地圖：{r['柱子']}", body, "docs/變更分級與柱子地圖.md", date=d, version=ver["版本"],
                        status=gstatus, sens="internal", date_note=note))
    return out


def corrections():
    c = load("corrections.zh.json")
    return [unit(e["code"], f"勘誤 {e['id']}：{e['page']}",
                 f"勘誤 {e['id']}（違反憲章{e['article']}）。發現 {e['found']}，修正 {e['fixed']}。錯在哪裡：{e['wrong']} 原因：{e['cause']} 怎麼修正：{e['fix']}",
                 "knowledge/corrections.zh.json", source=[["修正紀錄", e["ref"]]], date=e["fixed"]) for e in c["items"]]


def sources():
    s = load("sources.json")
    out = []
    for i, e in enumerate(s["ingest"], 1):
        year = f"，{e['year']} 年" if e.get("year") else ""
        where = f"Gutenberg 書號 {e['gutenberg_id']}" if e.get("gutenberg_id") else f"網址 {e['url']}"
        link = f"https://www.gutenberg.org/ebooks/{e['gutenberg_id']}" if e.get("gutenberg_id") else e["url"]
        body = (f"可放進 AI 系統的來源：{e['title']}，作者 {e['author']}{year}，{where}，授權：{e['license']}。"
                f"對應理專：{'、'.join(ADV[a][1] for a in e.get('advisors', []) if a in ADV)}。主題：{'、'.join(e.get('topics', []))}。")
        out.append(unit(f"SRC-ING-{i:02d}", f"來源授權：{e['title']}", body, "knowledge/sources.json",
                        source=[["原始出處", link]], date=s["checked_on"]))
    for i, e in enumerate(s["read_only"], 1):
        body = f"只給人閱讀、不可放進 AI 系統的教材：{e['title']}（{e['publisher']}），授權：{e['license']}。理由：{e['why']}"
        out.append(unit(f"SRC-RO-{i:02d}", f"來源授權（僅供閱讀）：{e['title']}", body, "knowledge/sources.json",
                        source=[[e["publisher"], e["url"]]], date=s["checked_on"]))
    return out


def insider():
    d = load("insider.zh.json")
    return [unit(it["code"], f"{s['title']}：{it['t']}", it["b"], "knowledge/insider.zh.json", source=it.get("src") or SELF, date=d["asof"])
            for s in d["sections"] for it in s["items"]]


def basics():
    d = load("basics.zh.json")
    f, a = "knowledge/basics.zh.json", d["asof"]
    out = [unit(p["code"], f"投資原則 {p['n']}：{p['t']}", f"{p['d']}（{p['who']}：「{p['say']}」）", f, date=a) for p in d["principles"]]
    out += [unit(p["code"], f"入門步驟：{p['t']}", p["d"], f, date=a) for p in d["steps"]]
    out += [unit(p["code"], f"名詞（{p['g']}）：{p['k']}", p["d"], f, date=a) for p in d["terms"]]
    out += [unit(p["code"], f"投資成本：{p['k']}", f"{p['v']}。{p['d']}", f, date=a) for p in d["costs"]]
    out += [unit(p["code"], f"常見迷思：{p['q']}", p["a"], f, date=a) for p in d["myths"]]
    return out


def advisors():
    d = load("advisors.zh.json")
    note = "原始檔案未記載資料日期，取 git 紀錄之最後修改日"
    out = []
    for k, (c, name, school) in ADV.items():
        p = d[k]
        body = (f"{name}（{school}）。經歷：{'；'.join(p['career'])}。在意的風險：{'；'.join(p['risk'])}。評判標準：{'；'.join(p['criteria'])}。"
                f"可取得的資料：{'、'.join(p['db'])}。盲點：{p['blind']} 適合客群：{p['client']}")
        out.append(unit(f"ADV-{c}-01", f"理專背景：{name}（{school}）", body, "knowledge/advisors.zh.json",
                        date=FILE_DATE["advisors.zh.json"], date_note=note))
    return out


def concepts_books():
    out = []
    note = "原始檔案未記載資料日期，取 git 紀錄之最後修改日"
    c = load("concepts.zh.json")
    for k, (_, name, _s) in ADV.items():
        for e in c[k]:
            out.append(unit(e["code"], f"概念卡（{name}）：{e['title']}", f"{e['body']} 怎麼用：{e['use']}", "knowledge/concepts.zh.json",
                            date=FILE_DATE["concepts.zh.json"], date_note=note))
    b = load("bookshelf.zh.json")
    for k, (_, name, _s) in ADV.items():
        for e in b[k]:
            out.append(unit(e["code"], f"課外書架（{name}）：{e['zh']}", f"《{e['zh']}》（{e['title']}），{e['author']}，{e['genre']}。特質：{e['trait']}。讀書心得：{e['idea']}",
                            "knowledge/bookshelf.zh.json", source=[["Project Gutenberg", f"https://www.gutenberg.org/ebooks/{e['gid']}"]],
                            date=FILE_DATE["bookshelf.zh.json"], date_note=note))
    return out


def public_units():
    return charter() + change_log() + corrections() + sources() + insider() + basics() + advisors() + concepts_books()


def private_units():
    """研究者電腦上的受限文件：kb-private/*.json，每檔是一個單元清單，欄位同 unit()；不進 git"""
    out = []
    for p in sorted(PRIVATE.glob("*.json")) if PRIVATE.exists() else []:
        if p.name == "catalog_full.json":
            continue
        out += json.loads(p.read_text(encoding="utf-8"))
    return out


def check(units):
    err = []
    seen = set()
    need = ("code", "layer", "category", "title", "text", "source", "date", "status", "roles", "sensitivity", "file")
    for u in units:
        if u["code"] in seen:
            err.append(f"代號重複：{u['code']}")
        seen.add(u["code"])
        if not CODE.match(u["code"]):
            err.append(f"代號格式不對：{u['code']}")
        for f in need:
            if u.get(f) in (None, "", []):
                err.append(f"{u['code']} 缺少 {f}")
        if not re.match(r"\d{4}-\d{2}-\d{2}$", u.get("date", "")):
            err.append(f"{u['code']} 資料日期格式不對：{u.get('date')}")
        if u["sensitivity"] != "公開" and u["layer"] in ("2", "3"):
            err.append(f"{u['code']} 第二、三層應為公開")
    return err


def catalog():
    units = public_units()
    by_layer = {lv: sum(1 for u in units if u["layer"] == lv) for lv in ("1", "2", "3")}
    return {"_note": "文件庫目錄（自動產生，請勿手改；改原始檔案後執行 python scripts/build_catalog.py）。CR-016。",
            "asof": max(u["date"] for u in units), "count": len(units), "by_layer": by_layer,
            "layers": TAXO["layers"], "roles": ROLES["roles"], "sensitivity": ROLES["sensitivity"], "refusal": ROLES["refusal"],
            "units": units}


def main():
    cat = catalog()
    err = check(cat["units"])
    priv = private_units()
    if priv:
        err += [e for e in check(cat["units"] + priv) if any(p["code"] in e for p in priv)]
    if err:
        print("\n".join("✗ " + e for e in err))
        sys.exit(1)
    text = json.dumps(cat, ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("✗ knowledge/governance/catalog.json 和原始檔案不一致，請執行 python scripts/build_catalog.py 後一起提交")
            sys.exit(1)
        print(f"ok  文件庫目錄 {cat['count']} 個單元，代號唯一、欄位齊全，與原始檔案一致")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"ok  {OUT.relative_to(ROOT)}（{cat['count']} 個單元：{cat['by_layer']}）")
    if priv:
        full = dict(cat, units=cat["units"] + priv, count=cat["count"] + len(priv))
        (PRIVATE / "catalog_full.json").write_text(json.dumps(full, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"ok  kb-private/catalog_full.json（另含 {len(priv)} 個受限單元，不進 git）")


if __name__ == "__main__":
    main()
