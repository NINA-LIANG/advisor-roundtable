"""文件庫共用的小工具：把憲章網頁原稿切成段落、讀 Markdown 表格（CR-016）。"""
import html
import re

TAG = re.compile(r"<[^>]+>")


def strip(s):
    s = re.sub(r"<(br|/p|/li|/tr)\s*/?>", "\n", s)
    s = re.sub(r"</t[dh]>", "　", s)
    return re.sub(r"[ \t]*\n[ \t\n]*", "\n", html.unescape(TAG.sub("", s))).strip()


def charter_sections(src):
    """憲章原稿 → [(標題, 內文)]，一個 <section class="box"> 是一段"""
    out = []
    for m in re.finditer(r'<section class="box">(.*?)</section>', src, re.S):
        body = m.group(1)
        h = re.search(r"<h2>(.*?)</h2>", body, re.S)
        out.append((strip(h.group(1)), strip(body[h.end():])))
    return out


def charter_version(src):
    m = re.search(r"Charter　(v[\d.]+)（(\d{4}-\d{2}-\d{2})）", src)
    return m.group(1), m.group(2)


def md_tables(text):
    """Markdown 裡的每一張表 → [[{欄名: 值}]]；值裡的 ` 與 ** 拿掉"""
    tables, cur = [], None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip().replace("`", "").replace("**", "") for c in line.strip().strip("|").split("|")]
            if cur is None:
                cur = {"head": cells, "rows": []}
            elif not set("".join(cells)) <= set("-: "):
                cur["rows"].append(dict(zip(cur["head"], cells)))
        elif cur is not None:
            tables.append(cur["rows"]); cur = None
    if cur is not None:
        tables.append(cur["rows"])
    return tables
