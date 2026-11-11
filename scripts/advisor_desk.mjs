// 理專辦公室（CR-010）：六位理專每天的工作日誌、圓桌對話、意見彙整報表、各自的 100 萬虛擬帳戶。
//
// 內容（股票、分數、理由、條件、互評警示）全部來自首頁同一份理專規則：
//   和 action_log.mjs、advisor_engine.mjs 一樣，直接從 web/index.template.html 切出
//   「台股資料～const TABS=」（六位理專）與「const REVIEWER=～function health(」（互評配對與檢查）執行。
// 語氣（開場白、口頭禪、盲點的說法）來自 knowledge/desk_voice.zh.json，屬憲章外層；
//   同一天、同一位理專挑同一句，所以同一份資料重算結果相同（憲章第六條「可檢驗」）。
// 互評只記錄、不改分數（憲章第二條「依規則」，需求者 2026-11-05 同意企劃）。
//
// 虛擬帳戶（憲章「模擬倉的定位」：報酬不作為評判理專好壞的依據）：
//   每人 100 萬，從第一次執行那天開始，不回補過去。
//   每週第一個交易日決定「本週前三名」，等權買進；平日持股被自己的規則判成「不看好」就決定賣出。
//   今天收盤後做的決定，用下一個交易日的收盤價成交，避免用已知的價格。
//   手續費 0.1425%（最低 20 元），賣出證交稅個股 0.3%、ETF 0.1%；可買零股。
//
// 輸出：data/desk.json（最近 30 個交易日的日誌、對話、報表）、data/advisor_books.json（六人帳戶）
// 句子出現憲章第三條禁語 → 結束碼 1（每日更新照常發佈，由通知步驟開 Issue）
// 用法：node scripts/advisor_desk.mjs
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import vm from "node:vm";

const ROOT = new URL("..", import.meta.url);
const read = p => readFileSync(new URL(p, ROOT), "utf8");
const readJSON = (p, d) => existsSync(new URL(p, ROOT)) ? JSON.parse(read(p)) : d;
const src = read("web/index.template.html");
const shared = src.slice(src.indexOf("// ---------- 台股資料"), src.indexOf("const TABS="));
const checksSrc = src.slice(src.indexOf("const REVIEWER="), src.indexOf("function health("));
const profiles = JSON.parse(read("knowledge/advisors.zh.json"));
export const VOICE = JSON.parse(read("knowledge/desk_voice.zh.json"));
const cfg = JSON.parse(read("knowledge/action_log.zh.json"));
const charter = read("web/charter.template.html");
export const BANNED = [...(charter.match(/<b>不保證<\/b>：不說((?:「[^」]+」)+)/)?.[1] || "").matchAll(/「([^」]+)」/g)].map(m => m[1]);

export const START_CASH = 1_000_000, FEE = 0.001425, FEE_MIN = 20, TAX_STOCK = 0.003, TAX_ETF = 0.001;
export const fee = amt => amt > 0 ? Math.max(FEE_MIN, Math.round(amt * FEE)) : 0;
export const tax = (amt, etf) => Math.round(amt * (etf ? TAX_ETF : TAX_STOCK));
const r2 = x => Math.round(x * 100) / 100;
// CR-014（2026-11-11）：標籤改成白話，分數門檻不變。舊紀錄裡的舊說法用 PLAIN 換成新說法再比較或顯示
export const LABEL = s => s >= 1.5 ? "很看好" : s >= 0.5 ? "有點看好" : s > -0.5 ? "不好不壞" : "不看好";
export const PLAIN = { "規則強烈偏多": "很看好", "規則偏多": "有點看好", "規則中性": "不好不壞", "規則偏空": "不看好" };
export const plain = t => typeof t === "string" ? t.replace(/規則強烈偏多|規則偏多|規則中性|規則偏空/g, m => PLAIN[m]) : t;
export const bucket = s => s >= 0.5 ? 1 : s <= -0.5 ? -1 : 0;
const strip = t => String(t ?? "").replace(/<[^>]+>/g, "");
const fill = (t, o) => t.replace(/\{(\w+)\}/g, (m, k) => (k in o ? String(o[k]) : m));
const hash = s => parseInt(createHash("sha256").update(s).digest("hex").slice(0, 8), 16);
const pick = (arr, seed) => arr[hash(seed) % arr.length];
const fmtP = x => x >= 1000 ? x.toFixed(0) : x >= 100 ? x.toFixed(1) : x.toFixed(2);
const mean = a => a.reduce((x, y) => x + y, 0) / a.length;
const std = a => { const m = mean(a); return Math.sqrt(mean(a.map(x => (x - m) ** 2))); };

// 這一週的星期一（UTC 日期字串），用來判斷「每週第一個交易日」
export function weekOf(d) {
  const t = new Date(d + "T00:00:00Z");
  t.setUTCDate(t.getUTCDate() - (t.getUTCDay() + 6) % 7);
  return t.toISOString().slice(0, 10);
}

// 在沙盒裡建立六位理專與互評檢查（和首頁同一份程式）
export function loadEngine(tw) {
  const code = shared.replace("/*TW*/", JSON.stringify(tw)).replace("/*PROFILES*/", JSON.stringify(profiles))
    .replace("/*SHELF*/", read("knowledge/bookshelf.zh.json")) + checksSrc + ";({ADVISORS,isETF,REVIEWER,CHECKS})";
  return vm.runInNewContext(code, {}, { timeout: 30000 });
}

// 理專只拿得到自己允許的欄位（加上代號、名稱）
function viewOf(d, allowed) {
  const v = { c: d.c, n: d.n };
  allowed.forEach(k => { if (k in d) v[k] = d[k]; });
  return v;
}

// 建立當天的意見查詢：opinion(key, code) → {s, label, why, entry, metrics}
export function makeContext(tw, macro = cfg.macro) {
  const E = loadEngine(tw);
  const byCode = Object.fromEntries([...tw.stocks, ...tw.etfs].map(s => [s.c, s]));
  const withMacro = s => ({ ...s, ...macro });
  const cache = new Map();
  const opinion = (key, c) => {
    const k = key + ":" + c;
    if (!cache.has(k)) {
      const a = E.ADVISORS.find(x => x.key === key), d = byCode[c];
      const r = d ? a.run(viewOf(withMacro(d), profiles[key]?.fields || [])) : null;
      cache.set(k, r ? { s: r.s, label: Number.isFinite(r.s) ? LABEL(r.s) : "無法判斷", why: (r.why || []).map(strip),
                         entry: strip(r.entry), metrics: r.metrics || {}, tb: r.tb } : null);
    }
    return cache.get(k);
  };
  // 和 action_log.mjs、首頁「理專選股」相同：全部個股、分數高到低、同分看 tb
  const top = key => tw.stocks.map(s => ({ c: s.c, ...opinion(key, s.c) }))
    .sort((x, y) => y.s - x.s || y.tb - x.tb).slice(0, cfg.top_n).map(x => x.c);
  const R = c => Object.fromEntries(E.ADVISORS.map(a => [a.key, opinion(a.key, c)]));
  return { E, byCode, withMacro, opinion, top, R, macro,
           keys: E.ADVISORS.map(a => a.key), nameOf: k => E.ADVISORS.find(a => a.key === k).name,
           price: c => byCode[c]?.p, isEtf: c => !!byCode[c] && E.isETF(byCode[c]), stockName: c => byCode[c]?.n || c };
}

// ---------- 虛擬帳戶 ----------
export function newAccount() { return { cash: START_CASH, pos: {}, pending: null, week: null }; }

// 執行前一個交易日做的決定（用今天 D 的收盤價成交）
export function execute(acct, D, ctx, trades) {
  const pend = acct.pending;
  if (!pend) return;
  const why = pend.why || {};
  const sells = new Set(pend.sell || []);
  if (pend.target) Object.keys(acct.pos).forEach(c => { if (!pend.target.includes(c)) sells.add(c); });
  const left = [];
  for (const c of sells) {
    const pos = acct.pos[c];
    if (!pos) continue;
    const p = ctx.price(c);
    if (!(p > 0)) { left.push(c); continue; }
    const amt = r2(pos.sh * p), f = fee(amt), t = tax(amt, ctx.isEtf(c));
    acct.cash = r2(acct.cash + amt - f - t);
    delete acct.pos[c];
    trades.push({ d: D, c, n: ctx.stockName(c), side: "賣", sh: pos.sh, p, fee: f, tax: t, pnl: Math.round(amt - f - t - pos.sh * pos.cost), why: why[c] || "", decided: pend.decided });
  }
  if (pend.target) {
    const buys = pend.target.filter(c => !acct.pos[c] && ctx.price(c) > 0);
    let n = buys.length;
    for (const c of buys) {
      const p = ctx.price(c), budget = acct.cash / n--;
      let sh = Math.floor(budget / (p * (1 + FEE)));
      while (sh > 0 && sh * p + fee(sh * p) > budget) sh--;
      if (sh <= 0) continue;
      const amt = r2(sh * p), f = fee(amt);
      acct.cash = r2(acct.cash - amt - f);
      acct.pos[c] = { sh, cost: r2((amt + f) / sh), since: D, n: ctx.stockName(c) };
      trades.push({ d: D, c, n: ctx.stockName(c), side: "買", sh, p, fee: f, tax: 0, why: why[c] || "", decided: pend.decided });
    }
  }
  acct.pending = left.length ? { sell: left, why, decided: pend.decided, kind: "sell" } : null;
}

export function navOf(acct, ctx) {
  return r2(acct.cash + Object.entries(acct.pos).reduce((s, [c, x]) => s + x.sh * (ctx.price(c) ?? x.cost), 0));
}

// 收盤後依自己的規則決定明天要做什麼
export function decide(acct, D, ctx, key) {
  const wk = weekOf(D), why = { ...(acct.pending?.why || {}) };
  if (acct.week !== wk) {
    acct.week = wk;
    const target = ctx.top(key);
    target.forEach(c => { why[c] = `本週前三名：${ctx.opinion(key, c).why[0] || ""}`; });
    Object.keys(acct.pos).filter(c => !target.includes(c)).forEach(c => { why[c] = "換股：不在本週前三名"; });
    acct.pending = { target, sell: acct.pending?.sell || [], why, decided: D, kind: "rebalance" };
    return;
  }
  const sell = Object.keys(acct.pos).filter(c => { const o = ctx.opinion(key, c); return o && o.s <= -0.5; });
  sell.forEach(c => { why[c] = `轉為不看好：${ctx.opinion(key, c).why[0] || ""}`; });
  const all = [...new Set([...(acct.pending?.sell || []), ...sell])];
  acct.pending = all.length ? { sell: all, why, decided: D, kind: "sell" } : null;
}

// 帳戶往前走一天；同一天重跑時，從前一天的狀態重算（結果相同）
export function stepBooks(books, D, ctx) {
  const clone = x => JSON.parse(JSON.stringify(x));
  let b = books ? clone(books) : null;
  if (!b) b = { start: D, asof: null, state: {}, prev: {}, nav: {}, trades: {}, ref: [] };
  if (b.asof === D) {
    b.state = clone(b.prev);
    for (const k in b.nav) b.nav[k] = b.nav[k].filter(x => x[0] !== D);
    for (const k in b.trades) b.trades[k] = b.trades[k].filter(x => x.d !== D);
    b.ref = b.ref.filter(x => x[0] !== D);
  }
  b.prev = clone(b.state);
  const today = {};
  for (const key of ctx.keys) {
    const acct = b.state[key] || (b.state[key] = newAccount());
    const trades = [];
    execute(acct, D, ctx, trades);
    (b.nav[key] ||= []).push([D, navOf(acct, ctx)]);
    (b.trades[key] ||= []).push(...trades);
    decide(acct, D, ctx, key);
    today[key] = trades;
  }
  if (ctx.price("0050") > 0) b.ref.push([D, ctx.price("0050")]);
  b.asof = D;
  return { books: b, today };
}

// ---------- 日誌 ----------
const L = (t, c = []) => ({ t, c: [...new Set(c)] });

function blindLine(key, ctx, codes, D) {
  const v = VOICE.advisors[key];
  for (const c of codes) {
    const o = ctx.opinion(key, c), d = ctx.byCode[c];
    if (!o || !d) continue;
    const n = `${c} ${d.n}`;
    if (key === "tech") {
      const ma3 = mean(d.m.slice(-3)), gap = Math.abs(d.ma / ma3 - 1);
      if (gap < 0.02) return L(fill(v.worry, { c: n, gap: (gap * 100).toFixed(1) + "%" }), [c]);
    } else if (key === "value") {
      const rel = parseFloat(o.metrics["同業比"]);
      if (rel < 70) return L(fill(v.worry, { c: n, rel: rel + "%" }), [c]);
    } else if (key === "mom") {
      const dist = parseFloat(o.metrics["距高點"]);
      if (dist > -3) return L(fill(v.worry, { c: n, dist: o.metrics["距高點"].replace("-", "") }), [c]);
    } else if (key === "quant") {
      const z = parseFloat(o.metrics.z);
      if (z < -1.5) return L(fill(v.worry, { c: n, z }), [c]);
    } else if (key === "div") {
      if ((d.dy || 0) > 8) return L(fill(v.worry, { c: n, dy: d.dy.toFixed(2) + "%" }), [c]);
    }
  }
  if (key === "macro") return L(fill(v.worry, { light: ctx.macro.light, pmi: ctx.macro.pmi }));
  return null;
}

// 掉出名單的股票可能不在今天的資料裡（成交值沒過門檻），這時只寫代號
const nm = (ctx, c) => ctx.byCode[c] ? `${c} ${ctx.byCode[c].n}` : c;

export function journal(key, ctx, D, prev, history, trades, acct, warned) {
  const v = VOICE.advisors[key], seed = D + key;
  const top = ctx.top(key);
  const watch = cfg.watchlist.filter(c => ctx.byCode[c]);
  const codes = [...new Set([...watch, ...top])];
  const labels = Object.fromEntries(codes.map(c => [c, ctx.opinion(key, c).label]));
  const seen = [L(fill(pick(v.open, seed + "open"), { d: D, n: Object.keys(ctx.byCode).length })),
                L(`資料：臺灣證券交易所 ${D} 收盤；總經條件用網站預設值（${ctx.macro.light}燈、利率${ctx.macro.rate > 0 ? "升息" : ctx.macro.rate < 0 ? "降息" : "持平"}、PMI ${ctx.macro.pmi}）。`)];
  const view = [];
  const topTxt = top.map(c => `${nm(ctx, c)}（${ctx.opinion(key, c).why[0] || labels[c]}）`).join("；");
  if (!prev) {
    view.push(L(pick(v.first, seed + "first")));
    view.push(L(`今天的前三名：${topTxt}。`, top));
  } else {
    const inn = top.filter(c => !prev.top.includes(c)), out = prev.top.filter(c => !top.includes(c));
    if (inn.length) view.push(L(`前三名換了：${inn.map(c => nm(ctx, c)).join("、")} 進來${out.length ? `，${out.map(c => nm(ctx, c)).join("、")} 掉出去` : ""}。`, [...inn, ...out]));
    else view.push(L(pick(v.same, seed + "same")));
    view.push(L(`今天的前三名：${topTxt}。`, top));
    const changed = codes.filter(c => prev.labels[c] && plain(prev.labels[c]) !== labels[c]);
    changed.forEach(c => view.push(L(`${nm(ctx, c)}：昨天「${plain(prev.labels[c])}」，今天「${labels[c]}」，${ctx.opinion(key, c).why[0] || ""}。`, [c])));
    let streak = 1;
    for (const h of history) { if (h.journals?.[key]?.top?.[0] === top[0]) streak++; else break; }
    if (streak >= 3) view.push(L(`${nm(ctx, top[0])} 已經連續 ${streak} 天排第一。`, [top[0]]));
  }
  const worry = [];
  const b = blindLine(key, ctx, top, D);
  if (b) worry.push(b);
  const trade = trades.map(t => L(`${t.side === "買" ? "買進" : "賣出"} ${t.n}（${t.c}）${t.sh} 股，成交價 ${fmtP(t.p)}，${t.why}`, [t.c]));
  if (!trades.length) trade.push(L("今天帳戶沒有成交。"));
  const pend = acct.pending;
  if (pend?.kind === "rebalance") trade.push(L(`本週換股：下一個交易日收盤買進 ${pend.target.map(c => nm(ctx, c)).join("、")}${Object.keys(acct.pos).filter(c => !pend.target.includes(c)).length ? `，賣出 ${Object.keys(acct.pos).filter(c => !pend.target.includes(c)).map(c => nm(ctx, c)).join("、")}` : ""}。`, [...pend.target, ...Object.keys(acct.pos)]));
  else if (pend?.sell?.length) trade.push(L(`下一個交易日收盤賣出 ${pend.sell.map(c => nm(ctx, c)).join("、")}，規則已轉為不看好。`, pend.sell));
  const plan = [];
  for (const c of top) { if (plan.length >= 2) break; const e = ctx.opinion(key, c).entry; if (e) plan.push(L(`${nm(ctx, c)}：${e.replace(/^規則條件：/, "")}`, [c])); }
  warned.forEach(w => plan.push(L(`同事提醒的 ${nm(ctx, w.c)}：${w.msg}`, [w.c])));
  return { key, name: ctx.nameOf(key), top, labels,
           lines: { seen, view, worry, trade, plan, sign: [L(pick(v.sign, seed + "sign"))] } };
}

// ---------- 圓桌對話 ----------
export function roundtable(ctx, D) {
  const T = VOICE.talk, { REVIEWER, CHECKS } = ctx.E, talks = [], warned = {};
  for (const key of ctx.keys) {
    const r = REVIEWER[key], top = ctx.top(key);
    // 先找有互評警示的那檔；都沒有就看第一名
    let c = top.find(x => CHECKS[key](ctx.R(x), ctx.withMacro(ctx.byCode[x])));
    const msg = c ? CHECKS[key](ctx.R(c), ctx.withMacro(ctx.byCode[c])) : null;
    c = c || top[0];
    const mine = ctx.opinion(key, c), theirs = ctx.opinion(r, c), name = nm(ctx, c), seed = D + key + c;
    const thread = { type: "review", by: r, on: key, c, etf: ctx.isEtf(c), msgs: [] };
    if (msg) {
      thread.risk = VOICE.risk_type[r];
      thread.msgs.push({ who: r, t: fill(pick(T.warn, seed + "w"), { c: name, msg }) });
      thread.msgs.push({ who: key, t: fill(pick(T.reply_warn, seed + "r"), { c: name, blind: profiles[key].blind }) });
      (warned[key] ||= []).push({ c, msg, by: r });
    } else {
      const same = bucket(mine.s) === bucket(theirs.s);
      thread.agree = same;
      thread.msgs.push({ who: r, t: fill(pick(same ? T.agree : T.differ, seed + "a"), { c: name, label: theirs.label, why: theirs.why[0] || "" }) });
      if (!same) thread.msgs.push({ who: key, t: pick(T.reply_differ, seed + "d") });
    }
    talks.push(thread);
  }
  // 分歧最大的 3 檔（最高分和最低分差 2 分以上），看好和不看好的各說一次
  const pool = [...new Set([...cfg.watchlist.filter(c => ctx.byCode[c]), ...ctx.keys.flatMap(k => ctx.top(k))])];
  const spread = pool.map(c => { const R = ctx.R(c), ks = ctx.keys.filter(k => Number.isFinite(R[k]?.s));
    const hi = ks.reduce((a, k) => R[k].s > R[a].s ? k : a, ks[0]), lo = ks.reduce((a, k) => R[k].s < R[a].s ? k : a, ks[0]);
    return { c, hi, lo, gap: R[hi].s - R[lo].s }; })
    .filter(x => x.gap >= 2).sort((a, b) => b.gap - a.gap || a.c.localeCompare(b.c)).slice(0, 3);
  for (const x of spread) {
    const name = nm(ctx, x.c), H = ctx.opinion(x.hi, x.c), Lo = ctx.opinion(x.lo, x.c), seed = D + x.c;
    talks.push({ type: "debate", c: x.c, etf: ctx.isEtf(x.c), gap: x.gap, msgs: [
      { who: x.hi, t: fill(pick(T.debate_bull, seed + "b"), { c: name, label: H.label, why: H.why[0] || "" }) },
      { who: x.lo, t: fill(pick(T.debate_bear, seed + "s"), { c: name, label: Lo.label, why: Lo.why[0] || "" }) }] });
  }
  return { talks, warned, pool };
}

// ---------- 意見彙整報表 ----------
export function report(ctx, pool, journals, talks, books, today, checksDay) {
  const rows = pool.map(c => { const R = ctx.R(c), s = Object.fromEntries(ctx.keys.map(k => [k, R[k]?.s]));
    const vals = Object.values(s).filter(Number.isFinite);
    return { c, n: ctx.stockName(c), etf: ctx.isEtf(c), s, bull: vals.filter(x => bucket(x) > 0).length,
             bear: vals.filter(x => bucket(x) < 0).length, sd: Math.round(std(vals) * 100) / 100 }; })
    .sort((a, b) => b.sd - a.sd || a.c.localeCompare(b.c));
  const unanimous = rows.filter(r => r.bull === 6 || r.bear === 6).map(r => r.c);
  const changes = Object.values(journals).flatMap(j => j.lines.view.filter(l => l.t.includes("昨天「")).map(l => ({ who: j.key, ...l })));
  const risks = {};
  talks.filter(t => t.risk).forEach(t => (risks[t.risk] ||= []).push({ by: t.by, on: t.on, c: t.c, etf: t.etf }));
  const acc = Object.fromEntries(ctx.keys.map(k => { const a = books.state[k], nav = books.nav[k].at(-1)[1];
    return [k, { nav, cash_pct: Math.round(a.cash / nav * 1000) / 10, n_hold: Object.keys(a.pos).length, trades_today: today[k].length }]; }));
  const checks = checksDay ? Object.fromEntries(Object.entries(checksDay.advisors).map(([k, v]) =>
    [k, { ok: Object.values(v.checks).filter(x => x.startsWith("✓")).length, total: Object.keys(v.checks).length,
          bad: Object.entries(v.checks).filter(([, x]) => x.startsWith("✗")).map(([n]) => n) }])) : null;
  return { rows, unanimous, changes, risks, accounts: acc, checks };
}

function allText(x) {
  if (typeof x === "string") return [x];
  if (Array.isArray(x)) return x.flatMap(allText);
  if (x && typeof x === "object") return Object.values(x).flatMap(allText);
  return [];
}
export const bannedIn = obj => { const t = allText(obj).join("\n"); return BANNED.filter(w => t.includes(w)); };

export function buildDay(tw, prevDesk, books, checksDay) {
  const D = tw.asof, ctx = makeContext(tw);
  const history = (prevDesk?.days || []).filter(d => d.asof < D);
  const prev = history[0] || null;
  const step = stepBooks(books, D, ctx);
  const { talks, warned, pool } = roundtable(ctx, D);
  const journals = Object.fromEntries(ctx.keys.map(k => [k, journal(k, ctx, D, prev?.journals?.[k] || null, history,
    step.today[k], step.books.state[k], warned[k] || [])]));
  const bull = pool.reduce((s, c) => s + ctx.keys.filter(k => bucket(ctx.opinion(k, c).s) > 0).length, 0);
  const bear = pool.reduce((s, c) => s + ctx.keys.filter(k => bucket(ctx.opinion(k, c).s) < 0).length, 0);
  const day = { asof: D, n: Object.keys(ctx.byCode).length, mood: { bull, bear, total: pool.length * ctx.keys.length },
                journals, talks, report: report(ctx, pool, journals, talks, step.books, step.today, checksDay) };
  return { day, books: step.books, ctx };
}

function main() {
  const tw = JSON.parse(read("data/tw.json"));
  const prevDesk = readJSON("data/desk.json", { days: [] });
  const books = readJSON("data/advisor_books.json", null);
  const mr = readJSON("data/morning_report.json", { days: [] });
  const checksDay = mr.days.find(d => d.asof === tw.asof) || null;
  const { day, books: nb } = buildDay(tw, prevDesk, books, checksDay);
  const days = [day, ...prevDesk.days.filter(d => d.asof !== day.asof)].sort((a, b) => b.asof.localeCompare(a.asof)).slice(0, cfg.keep_days);
  writeFileSync(new URL("data/desk.json", ROOT), JSON.stringify({ asof: tw.asof, keep_days: cfg.keep_days, days }));
  writeFileSync(new URL("data/advisor_books.json", ROOT), JSON.stringify(nb));
  for (const [k, j] of Object.entries(day.journals)) {
    const nav = nb.nav[k].at(-1)[1];
    console.log(`${j.name}（${k}）前三名 ${j.top.join("、")}；帳戶淨值 ${nav.toLocaleString()}；今天成交 ${day.report.accounts[k].trades_today} 筆`);
  }
  console.log(`對話 ${day.talks.length} 串；全員一致 ${day.report.unanimous.length} 檔`);
  const hit = bannedIn(day);
  if (hit.length) { console.error(`日誌或對話出現禁語：${hit.join("、")}`); process.exit(1); }
  console.log(`ok  ${tw.asof} 理專辦公室已更新`);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split("/").pop())) main();
