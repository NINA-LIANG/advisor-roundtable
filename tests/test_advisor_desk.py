"""理專辦公室（CR-010）：日誌、對話、報表、六人虛擬帳戶"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="需要 Node")


def node(js):
    code = (f'Promise.all([import("./scripts/advisor_desk.mjs"),import("node:fs")]).then(([m,fs])=>'
            f'{{const out=({js});console.log(JSON.stringify(out))}})')
    r = subprocess.run(["node", "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# 假的當天環境：價格與意見都由測試指定，只測帳戶的算術與流程
FAKE = """const fake=(prices,opinions,top)=>({keys:["tech"],price:c=>prices[c],isEtf:c=>c.startsWith("00"),
  stockName:c=>"股"+c,top:()=>top,opinion:(k,c)=>({s:opinions[c]??1,why:["理由"+c]})});"""


def test_fee_and_tax():
    out = node("[m.fee(10000),m.fee(1000000),m.fee(0),m.tax(100000,false),m.tax(100000,true)]")
    assert out == [20, 1425, 0, 300, 100]


def test_week_of_is_monday():
    out = node('[m.weekOf("2026-11-05"),m.weekOf("2026-11-02"),m.weekOf("2026-11-08"),m.weekOf("2026-11-09")]')
    assert out == ["2026-11-02", "2026-11-02", "2026-11-02", "2026-11-09"]


def test_books_decide_today_trade_next_day_and_keep_the_money_right():
    out = node("""(()=>{""" + FAKE + """
      let b=null,log=[];
      // 週四：第一次執行，決定買 A、B、C，當天不成交
      let s=m.stepBooks(b,"2026-11-05",fake({A:100,B:50,C:20},{},["A","B","C"]));b=s.books;log.push(s.today.tech.length);
      // 週五：用週五的收盤價成交；C 被規則判成偏空 → 決定隔天賣
      s=m.stepBooks(b,"2026-11-06",fake({A:110,B:50,C:20},{C:-1},["A","B","C"]));b=s.books;log.push(s.today.tech.length);
      const afterBuy=JSON.parse(JSON.stringify(b.state.tech)),fri=JSON.stringify(b);
      // 週五重跑一次：結果要完全一樣
      const again=m.stepBooks(b,"2026-11-06",fake({A:110,B:50,C:20},{C:-1},["A","B","C"])).books;
      // 下週一：先賣 C（用週一價格），再決定本週換股
      s=m.stepBooks(b,"2026-11-09",fake({A:120,B:40,C:25,D:10},{},["A","D","B"]));b=s.books;
      return {log,afterBuy,same:JSON.stringify(again)===fri,
              trades:b.trades.tech,nav:b.nav.tech,state:b.state.tech}})()""")
    assert out["log"] == [0, 3]
    buy = [t for t in out["trades"] if t["side"] == "買"]
    assert [t["c"] for t in buy] == ["A", "B", "C"] and all(t["d"] == "2026-11-06" and t["decided"] == "2026-11-05" for t in buy)
    assert buy[0]["p"] == 110  # 用成交日（週五）的價格，不是做決定那天的 100
    pos = out["afterBuy"]["pos"]
    spent = sum(t["sh"] * t["p"] + t["fee"] for t in buy)
    assert abs(out["afterBuy"]["cash"] - (1_000_000 - spent)) < 0.01
    assert out["afterBuy"]["cash"] >= 0 and set(pos) == {"A", "B", "C"}
    # 等權：三檔的金額相差不到 0.1%（整股取整與手續費造成的零頭）
    vals = [pos[c]["sh"] * p for c, p in (("A", 110), ("B", 50), ("C", 20))]
    assert (max(vals) - min(vals)) / max(vals) < 0.001
    assert out["same"]
    sell = [t for t in out["trades"] if t["side"] == "賣"]
    assert sell[0]["c"] == "C" and sell[0]["d"] == "2026-11-09" and sell[0]["p"] == 25
    assert sell[0]["tax"] == round(sell[0]["sh"] * 25 * 0.003) and "不看好" in sell[0]["why"]
    # 週一決定換股（A、D、B），還沒成交
    assert out["state"]["pending"]["kind"] == "rebalance" and out["state"]["pending"]["target"] == ["A", "D", "B"]
    # 淨值＝現金＋持股市值
    st = out["state"]
    mv = sum(x["sh"] * {"A": 120, "B": 40}[c] for c, x in st["pos"].items())
    assert abs(out["nav"][-1][1] - (st["cash"] + mv)) < 0.01


def _day():
    return node("""(()=>{const tw=JSON.parse(fs.readFileSync("data/tw.json","utf8"));
      const one=m.buildDay(tw,{days:[]},null,null).day, two=m.buildDay(tw,{days:[]},null,null).day;
      return {day:one,same:JSON.stringify(one)===JSON.stringify(two),banned:m.bannedIn(one),
              watch:JSON.parse(fs.readFileSync("knowledge/action_log.zh.json","utf8")).watchlist}})()""")


@pytest.fixture(scope="module")
def day():
    return _day()


def test_real_day_is_reproducible_and_clean(day):
    assert day["same"], "同一份資料重算，日誌與對話要完全相同"
    assert day["banned"] == []
    d = day["day"]
    assert len(d["journals"]) == 6
    assert sum(t["type"] == "review" for t in d["talks"]) == 6
    assert sum(t["type"] == "debate" for t in d["talks"]) <= 3
    for j in d["journals"].values():
        assert len(j["top"]) == 3
        assert all(j["lines"][k] for k in ("seen", "view", "trade", "sign"))


def test_lines_tag_every_stock_they_mention(day):
    """保守型使用者看不到個股內容：每句話提到的代號都要列在 c，頁面才擋得到"""
    d = day["day"]
    codes = {r["c"] for r in d["report"]["rows"]}
    for j in d["journals"].values():
        for k, lines in j["lines"].items():
            for line in lines:
                for c in re.findall(r"\b\d{4,6}[A-Z]?\b", line["t"]):
                    if c in codes:
                        assert c in line["c"], (j["key"], k, line["t"])
    for t in d["talks"]:
        assert "etf" in t and t["c"] in codes


def test_review_pairs_follow_homepage_reviewer(day):
    src = (ROOT / "web" / "index.template.html").read_text(encoding="utf-8")
    pairs = dict(re.findall(r'(\w+):"(\w+)"', re.search(r"const REVIEWER=\{([^}]+)\}", src).group(1)))
    for t in day["day"]["talks"]:
        if t["type"] == "review":
            assert pairs[t["on"]] == t["by"]
            assert t["msgs"][0]["who"] == t["by"]


def test_top_picks_match_action_log():
    """和晨報的前三名同一份規則、同一種排序"""
    log = json.loads((ROOT / "data" / "action_log.json").read_text(encoding="utf-8"))
    tw = json.loads((ROOT / "data" / "tw.json").read_text(encoding="utf-8"))
    if log["asof"] != tw["asof"]:
        pytest.skip("晨報與台股資料不同天")
    out = node("""(()=>{const tw=JSON.parse(fs.readFileSync("data/tw.json","utf8"));const ctx=m.makeContext(tw);
      return Object.fromEntries(ctx.keys.map(k=>[k,ctx.top(k)]))})()""")
    for k, v in log["advisors"].items():
        assert out[k] == v["top"], k


def test_peer_warning_does_not_change_scores(day):
    """憲章第二條：被同事提醒後只記錄，報表裡的分數就是理專自己規則的分數"""
    out = node("""(()=>{const tw=JSON.parse(fs.readFileSync("data/tw.json","utf8"));const ctx=m.makeContext(tw);
      return Object.fromEntries(["2330","0050","2882"].map(c=>[c,Object.fromEntries(ctx.keys.map(k=>[k,ctx.opinion(k,c).s]))]))})()""")
    rows = {r["c"]: r["s"] for r in day["day"]["report"]["rows"]}
    for c, s in out.items():
        if c in rows:
            assert rows[c] == s


def test_voice_has_no_banned_words():
    voice = (ROOT / "knowledge" / "desk_voice.zh.json").read_text(encoding="utf-8")
    for w in ("保證獲利", "穩賺", "一定會漲"):
        assert w not in voice



def test_backfill_marks_past_days_and_matches_running_daily():
    """CR-011：補記每天只用當天快照，結果和每天實際跑一次相同；今天以前的日誌標成補記"""
    js = """import * as m from "./scripts/advisor_desk.mjs"; import * as b from "./scripts/backfill_desk.mjs"; import fs from "node:fs";
      const base=JSON.parse(fs.readFileSync("data/tw.json","utf8"));
      const f2=(a,f)=>a.map(s=>({...s,p:+(s.p*f).toFixed(2)}));
      const day=(asof,f)=>({...base,asof,stocks:f2(base.stocks,f),etfs:f2(base.etfs,f)});
      const snaps=[day("2026-10-22",1),day("2026-10-27",1.01),day("2026-10-29",0.98)];
      const r=b.backfill(snaps,{days:[]},"2026-10-29");
      let desk={days:[]},books=null;for(const t of snaps){const x=m.buildDay(t,desk,books,null);desk={days:[x.day,...desk.days]};books=x.books}
      console.log(JSON.stringify({flags:r.desk.days.map(d=>[d.asof,!!d.backfill]),first:r.desk.days.at(-1).journals.tech.lines.seen[0].t,
        bf:r.books.backfill,sameNav:JSON.stringify(r.books.nav)===JSON.stringify(books.nav),
        sameTrades:JSON.stringify(r.books.trades)===JSON.stringify(books.trades),trades:r.books.trades.tech.length}))"""
    p = subprocess.run(["node", "--input-type=module", "-e", js], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["flags"] == [["2026-10-29", False], ["2026-10-27", True], ["2026-10-22", True]]
    assert out["first"].startswith("（補記") and "2026-10-22" in out["first"]
    assert out["bf"] == {"from": "2026-10-22", "to": "2026-10-29", "dates": ["2026-10-22", "2026-10-27", "2026-10-29"]}
    assert out["sameNav"] and out["sameTrades"] and out["trades"] > 0
