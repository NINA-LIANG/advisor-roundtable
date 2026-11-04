"""理專憲章的機器閘門：憲章寫的規則，盡量交給測試檢查，不靠人記得。

第三條「不保證」：禁語清單直接從憲章頁讀，改憲章就會改到這裡的檢查。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "web" / "charter.template.html"

# 網站上所有會被使用者讀到的文字來源（產生出來的 web/*.html 由這些組成，不重複掃）
SOURCES = sorted([*ROOT.glob("web/*.template.html"), ROOT / "web" / "kb.js", ROOT / "web" / "_shared.js",
                  *ROOT.glob("knowledge/*.json"), ROOT / "scripts" / "advisor_engine.mjs",
                  ROOT / "scripts" / "build_site.py"])

# 允許出現禁語的地方：必須是在提醒或反駁這句話，而不是理專自己這樣說。每一筆都要寫理由。
ALLOWED = {
    "charter.template.html": [("不說「保證獲利」「穩賺」「一定會漲」", "憲章本身列出禁語")],
    "basics.zh.json": [("「穩賺不賠」，通常是詐騙的警訊", "入門教室提醒這是詐騙警訊"),
                       ("跌深了就一定會漲回來？", "入門教室破解迷思的問題，答案說明個股不一定")],
    "corrections.zh.json": [("都寫著「省下的費用就是穩賺的報酬」", "勘誤紀錄引用被修正的原句")],
}


def banned_words():
    html = CHARTER.read_text(encoding="utf-8")
    m = re.search(r"<b>不保證</b>：不說((?:「[^」]+」)+)", html)
    assert m, "找不到憲章第三條「不保證」的禁語清單"
    return re.findall(r"「([^」]+)」", m.group(1))


def test_charter_lists_banned_words():
    assert banned_words() == ["保證獲利", "穩賺", "一定會漲"]


def test_site_text_has_no_banned_words():
    words = banned_words()
    hits = []
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        allowed = [a for a, _ in ALLOWED.get(path.name, [])]
        spans = [(m.start(), m.end()) for a in allowed for m in re.finditer(re.escape(a), text)]
        for w in words:
            for m in re.finditer(re.escape(w), text):
                if any(s <= m.start() and m.end() <= e for s, e in spans):
                    continue
                line = text.count("\n", 0, m.start()) + 1
                hits.append(f"{path.relative_to(ROOT)}:{line}「{w}」…{text[max(0, m.start() - 20):m.end() + 20]}…")
    assert not hits, "違反理專憲章第三條「不保證」：\n" + "\n".join(hits)


def test_conservative_kyc_blocks_stock_opinions_on_homepage():
    """第四條「守風險」：保守型＋個股時，單檔意見、理專選股、扭蛋都要先檢查，不產生意見"""
    src = (ROOT / "web" / "index.template.html").read_text(encoding="utf-8")
    assert 'const KYC_BLOCK="保守型"' in src
    render = src[src.index("function render(){"):src.index("\n", src.index("function render(){") + 60)]
    assert render.index("kycBlocked(state)") < render.index("drawChart") + 40, "render() 要在算理專意見之前先檢查 KYC"
    assert "if(kycBlocked(state)){" in src[src.index("function renderCards(){"):][:80]
    picks = src[src.index("function renderPicks(){"):][:120]
    assert 'uni==="stock"&&store.get("kyc",null)===KYC_BLOCK' in picks
    levels = [l["name"] for l in __import__("json").loads((ROOT / "knowledge" / "insider.zh.json").read_text(encoding="utf-8"))["quiz"]["levels"]]
    assert "保守型" in levels, "KYC 等級名稱改了，KYC_BLOCK 要跟著改"
