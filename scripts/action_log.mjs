// 理專憲章第六條「可檢驗」：每位理專每天留下動作紀錄，並產生晨報。
// 規則只有一份：和 advisor_engine.mjs 一樣，直接從首頁模板切出六位理專的規則執行。
//
// 記錄：固定觀察清單（knowledge/action_log.zh.json）＋每位理專當天個股前三名
// 每位理專每檔記：可用欄位、實際讀到的欄位（用 Proxy 記錄）、輸入數字、分數、看法、理由、進場說明
// 晨報檢查（每位理專一列）：
//   fields   只讀了允許的欄位（advisors.zh.json 的 fields，加上代號、名稱）
//   range    分數是有限數字，且在 −2～+2
//   words    理由與進場說明沒有憲章第三條禁語
//   data     當天輸入數字已和證交所公告比對一致（data/crosscheck.json）
//   repeat   同一份資料重算一次，結果完全相同
//   logged   今天有這位理專的紀錄
// 輸出：data/action_log.json（今天的完整紀錄）、data/morning_report.json（最近 N 天的晨報）
// 有任何 ✗ → 結束碼 1：每日更新照常發佈，但會開 Issue 通知（需求者 2026-11-04 決定）
// 用法：node scripts/action_log.mjs
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import vm from "node:vm";
import { ENGINE_SHA } from "./advisor_engine.mjs";

const ROOT = new URL("..", import.meta.url);
const read = p => readFileSync(new URL(p, ROOT), "utf8");
const src = read("web/index.template.html");
const shared = src.slice(src.indexOf("// ---------- 台股資料"), src.indexOf("const TABS="));
const cfg = JSON.parse(read("knowledge/action_log.zh.json"));
const tw = JSON.parse(read("data/tw.json"));
const profiles = JSON.parse(read("knowledge/advisors.zh.json"));
const charter = read("web/charter.template.html");
const banned = [...(charter.match(/<b>不保證<\/b>：不說((?:「[^」]+」)+)/)?.[1] || "").matchAll(/「([^」]+)」/g)].map(m => m[1]);

export const LABEL = s => s >= 1.5 ? "規則強烈偏多" : s >= 0.5 ? "規則偏多" : s > -0.5 ? "規則中性" : "規則偏空";

// 在沙盒裡建立 ADVISORS（和首頁同一份程式），回傳 { ADVISORS, isETF }
export function loadAdvisors(twData = tw) {
  const code = shared.replace("/*TW*/", JSON.stringify(twData)).replace("/*PROFILES*/", JSON.stringify(profiles))
    .replace("/*SHELF*/", read("knowledge/bookshelf.zh.json")) + ";({ADVISORS,isETF})";
  return vm.runInNewContext(code, {}, { timeout: 30000 });
}

// 跑一位理專一檔股票，記錄實際讀到的欄位
export function runOne(a, d, allowed) {
  const v = { c: d.c, n: d.n };
  allowed.forEach(k => { if (k in d) v[k] = d[k]; });
  const used = new Set();
  // 理專程式讀到「沒有被給的欄位」也要記下來，才看得出越權
  const full = { ...d };
  const proxy = new Proxy(v, { get(t, k) { if (typeof k === "string") used.add(k); return k in t ? t[k] : undefined; },
                               has(t, k) { if (typeof k === "string") used.add(k); return k in t; } });
  const r = a.run(proxy);
  const inputs = {};
  [...used].filter(k => k in full && typeof full[k] !== "object").forEach(k => inputs[k] = full[k]);
  return { used: [...used].sort(), inputs, s: r.s, label: Number.isFinite(r.s) ? LABEL(r.s) : "無法判斷",
           why: r.why, entry: r.entry };
}

export function checkAdvisor(a, items, rerun, crosscheckOk) {
  const allowed = new Set(["c", "n", ...(profiles[a.key]?.fields || [])]);
  const extra = [...new Set(items.flatMap(x => x.used))].filter(k => !allowed.has(k) && k !== "then" && k !== "toJSON");
  const badRange = items.filter(x => !Number.isFinite(x.s) || Math.abs(x.s) > 2);
  const text = items.flatMap(x => [...(x.why || []), x.entry || ""]).join("\n");
  const hitWords = banned.filter(w => text.includes(w));
  const same = JSON.stringify(items.map(({ s, why, entry }) => [s, why, entry])) ===
               JSON.stringify(rerun.map(({ s, why, entry }) => [s, why, entry]));
  return {
    fields: extra.length ? `✗ 讀了不允許的欄位：${extra.join("、")}` : "✓",
    range: badRange.length ? `✗ ${badRange.map(x => `${x.c} 分數 ${x.s}`).join("、")}` : "✓",
    words: hitWords.length ? `✗ 出現禁語：${hitWords.join("、")}` : "✓",
    data: crosscheckOk === true ? "✓" : crosscheckOk === false ? "✗ 當天數字和證交所公告不符" : "— 當天沒有比對紀錄",
    repeat: same ? "✓" : "✗ 同樣資料重算結果不同",
    logged: items.length ? "✓" : "✗ 今天沒有紀錄",
  };
}

function crosscheckStatus() {
  const p = new URL("data/crosscheck.json", ROOT);
  if (!existsSync(p)) return null;
  const c = JSON.parse(readFileSync(p, "utf8"));
  if (c.asof !== tw.asof || c.skipped) return null;
  return (c.mismatches || []).length === 0;
}

function main() {
  const { ADVISORS, isETF } = loadAdvisors();
  const byCode = Object.fromEntries([...tw.stocks, ...tw.etfs].map(s => [s.c, s]));
  const withMacro = s => ({ ...s, ...cfg.macro });
  const cc = crosscheckStatus();
  const log = { asof: tw.asof, engine_sha: ENGINE_SHA, macro: cfg.macro, watchlist: cfg.watchlist, advisors: {} };
  const day = { asof: tw.asof, engine_sha: ENGINE_SHA, advisors: {} };
  let fails = 0;
  for (const a of ADVISORS) {
    const allowed = profiles[a.key]?.fields || [];
    const run = codes => codes.map(c => ({ c, n: byCode[c].n, ...runOne(a, withMacro(byCode[c]), allowed) }));
    // 當天個股前三名（和首頁「理專選股」同樣用全部個股、同樣的排序）
    const ranked = tw.stocks.map(s => ({ c: s.c, ...a.run((() => { const d = withMacro(s), v = { c: d.c, n: d.n };
      allowed.forEach(k => { if (k in d) v[k] = d[k]; }); return v; })()) }))
      .sort((x, y) => y.s - x.s || y.tb - x.tb).slice(0, cfg.top_n).map(x => x.c);
    const codes = [...new Set([...cfg.watchlist.filter(c => byCode[c]), ...ranked])];
    const items = run(codes);
    const checks = checkAdvisor(a, items, run(codes), cc);
    const bad = Object.values(checks).filter(v => v.startsWith("✗")).length;
    fails += bad;
    log.advisors[a.key] = { name: a.name, allowed, top: ranked, items };
    // CR-004：格子圖點開時要看得到當天對觀察清單的看法與讀到的欄位，所以晨報也存一份摘要（保留 30 天）
    const w = items.filter(x => cfg.watchlist.includes(x.c)).map(x => [x.c, x.n, x.label, x.used.filter(k => k !== "c" && k !== "n")]);
    day.advisors[a.key] = { name: a.name, checks, n: items.length, w };
  }
  writeFileSync(new URL("data/action_log.json", ROOT), JSON.stringify(log));
  const rp = new URL("data/morning_report.json", ROOT);
  const old = existsSync(rp) ? JSON.parse(readFileSync(rp, "utf8")).days : [];
  const days = [day, ...old.filter(d => d.asof !== day.asof)].slice(0, cfg.keep_days);
  writeFileSync(rp, JSON.stringify({ asof: tw.asof, keep_days: cfg.keep_days, days }, null, 1));
  for (const [k, v] of Object.entries(day.advisors))
    console.log(`${v.name}（${k}）${Object.entries(v.checks).map(([c, r]) => `${c}:${r[0]}`).join(" ")}`);
  if (fails) { console.error(`晨報有 ${fails} 項 ✗，請查看 morning_report.json`); process.exit(1); }
  console.log(`ok  ${tw.asof} 六位理專的紀錄與晨報檢查全部通過`);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split("/").pop())) main();
