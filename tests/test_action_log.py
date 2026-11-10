"""每日動作紀錄與晨報（憲章第六條「可檢驗」）：檢查會不會真的抓到理專不依規則"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="需要 Node")


def node(js):
    code = (f'Promise.all([import("./scripts/action_log.mjs"),import("node:fs")]).then(([m,fs])=>'
            f'{{const out=({js});console.log(JSON.stringify(out))}})')
    r = subprocess.run(["node", "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_flags_reading_a_field_not_allowed():
    # value 只被允許看 p、pe、pb、i、t；故意讓它讀殖利率 dy
    out = node("""(()=>{const a={key:"value",run:d=>({s:d.dy>5?1:0,why:["看殖利率"],entry:""})};
      const items=[{c:"2330",...m.runOne(a,{c:"2330",n:"台積電",p:1,dy:6},["p","pe"])}];
      return m.checkAdvisor(a,items,items,true)})()""")
    assert out["fields"].startswith("✗") and "dy" in out["fields"]


def test_flags_banned_word_bad_score_and_nondeterminism():
    out = node("""(()=>{const a={key:"tech"};
      const items=[{c:"1",s:NaN,why:["這檔穩賺"],entry:""}], again=[{c:"1",s:1,why:["這檔穩賺"],entry:""}];
      return m.checkAdvisor(a,items,again,false)})()""")
    assert out["words"].startswith("✗") and "穩賺" in out["words"]
    assert out["range"].startswith("✗") and out["repeat"].startswith("✗") and out["data"].startswith("✗")


def test_real_advisors_pass_on_current_data():
    """六位理專照現在的規則，對目前資料的觀察清單都要通過欄位、分數、禁語、重算檢查（不寫檔）"""
    out = node("""(()=>{const P=JSON.parse(fs.readFileSync("knowledge/advisors.zh.json","utf8")),cfg=JSON.parse(fs.readFileSync("knowledge/action_log.zh.json","utf8"));
      const tw=JSON.parse(fs.readFileSync("data/tw.json","utf8")),by=Object.fromEntries([...tw.stocks,...tw.etfs].map(s=>[s.c,s]));
      const {ADVISORS}=m.loadAdvisors();const res={};
      for(const a of ADVISORS){const run=()=>cfg.watchlist.filter(c=>by[c]).map(c=>({c,...m.runOne(a,{...by[c],...cfg.macro},P[a.key].fields)}));
        res[a.key]=m.checkAdvisor(a,run(),run(),true)}return res})()""")
    assert len(out) == 6
    for key, checks in out.items():
        assert not any(v.startswith("✗") for v in checks.values()), (key, checks)


def test_morning_report_keeps_watchlist_summary_for_grid():
    """CR-004：格子圖點開要看得到當天觀察清單的看法與讀到的欄位"""
    import json
    from pathlib import Path
    r = json.loads((Path(__file__).resolve().parent.parent / "data" / "morning_report.json").read_text(encoding="utf-8"))
    a = next(iter(r["days"][0]["advisors"].values()))
    assert a["w"] and all(len(x) == 4 and x[2] and isinstance(x[3], list) for x in a["w"])
    assert all("c" not in x[3] and "n" not in x[3] for x in a["w"])


# ---- CR-013：每一項晨報檢查都要「真的會失敗」（2026-11-05 健康檢查發現其中三項在設計上不會出現 ✗）----

def test_banned_list_is_read_from_charter():
    """禁語清單讀自憲章第三條；讀不到（清單空白）時不能讓所有理專都顯示通過"""
    out = node("m.BANNED")
    assert "穩賺" in out and len(out) >= 3


def test_words_fails_when_banned_list_missing():
    out = node("""(()=>{const a={key:"tech"};const items=[{c:"1",s:1,why:["這檔穩賺"],entry:""}];
      return m.checkAdvisor(a,items,items,true,{banned:[]})})()""")
    assert out["words"].startswith("✗") and "禁語清單" in out["words"]


def test_data_fails_without_crosscheck_record():
    """沒有當天和證交所比對的紀錄＝沒有證據，不能顯示成通過或灰點"""
    out = node("""(()=>{const a={key:"tech"};const items=[{c:"1",s:1,why:[],entry:""}];
      return m.checkAdvisor(a,items,items,null)})()""")
    assert out["data"].startswith("✗")


def test_logged_fails_when_watchlist_stock_has_no_record():
    out = node("""(()=>{const a={key:"tech"};const items=[{c:"2330",s:1,why:[],entry:""}];
      return m.checkAdvisor(a,items,items,true,{expected:["2330","0050"]})})()""")
    assert out["logged"].startswith("✗") and "0050" in out["logged"]
    out = node("""(()=>{const a={key:"tech"};return m.checkAdvisor(a,[],[],true)})()""")
    assert out["logged"].startswith("✗")


def test_morning_report_applies_homepage_etf_rule():
    """首頁對槓桿反向、期貨型 ETF 一律最多給 −1；晨報要用同一份規則，不能出現首頁偏空、晨報偏多"""
    out = node("""(()=>{const {ADVISORS,runA}=m.loadAdvisors();const a={...ADVISORS[0],run:()=>({s:2,why:["假設規則給滿分"],entry:""})};
      const d={c:"00632R",n:"反向ETF",i:"ETF",t:"槓桿反向",p:10};
      return [m.runOne(a,d,["p"],runA).s, m.runOne(a,{...d,t:"市值型"},["p"],runA).s]})()""")
    assert out == [-1, 2]
