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
