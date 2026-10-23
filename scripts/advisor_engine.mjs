// 在 Node 裡跑首頁（web/index.template.html）同一份六位理專規則，給論文實驗的歷史題目離線計算用。
// 規則只有一份：直接從首頁模板切出「台股資料～const TABS=」與「const REVIEWER=～function health(」兩段執行，
// 首頁改規則時，重建題庫就會跟著改（題庫的 engine_sha 也會變）。
//
// 用法：node scripts/advisor_engine.mjs < input.json > output.json
// 輸入：{"dates":[{"date":"YYYYMMDD","light":"藍","rate":1,"pmi":48.2,"stocks":[{c,n,i,p,ma,m,tv,pe,dy,pb}]}]}
//       pmi 沒有資料就不要給這個欄位（理專會略過 PMI 這一項）
// 輸出：{"engine_sha":"…","dates":[{"date":…,"results":{代號:{tech:{s,why,entry,metrics},…,"alerts":[…]}}}]}
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import vm from "node:vm";

const ROOT = new URL("..", import.meta.url);
const src = readFileSync(new URL("web/index.template.html", ROOT), "utf8");
const shared = src.slice(src.indexOf("// ---------- 台股資料"), src.indexOf("const TABS="));
const checks = src.slice(src.indexOf("const REVIEWER="), src.indexOf("function health("));
const profiles = readFileSync(new URL("knowledge/advisors.zh.json", ROOT), "utf8");
const shelf = readFileSync(new URL("knowledge/bookshelf.zh.json", ROOT), "utf8");
export const ENGINE_SHA = createHash("sha256").update(shared + checks).digest("hex").slice(0, 16);

// 每個日期用當天的全部股票當 TW，產業本益比中位數（IND_PE）才會是那一天的同業比較
function runDate(day) {
  const tw = { asof: day.date, dates: [day.date], stocks: day.stocks, etfs: [] };
  const code = shared.replace("/*TW*/", JSON.stringify(tw)).replace("/*PROFILES*/", profiles).replace("/*SHELF*/", shelf)
    + checks
    + `;(()=>{const out={};for(const st of TW.stocks){const d={...st,light:MACRO.light,rate:MACRO.rate};
        if(MACRO.pmi!=null)d.pmi=MACRO.pmi;const R={};
        for(const a of ADVISORS){const r=a.run(d);R[a.key]={s:r.s,why:r.why,entry:r.entry,metrics:r.metrics}}
        const alerts=[];for(const a of ADVISORS){const m=CHECKS[a.key](R,d);if(m)alerts.push({by:REVIEWER[a.key],on:a.key,msg:m})}
        out[st.c]={...R,alerts}}return out})()`;
  const macro = { light: day.light, rate: day.rate, pmi: day.pmi ?? null };
  return vm.runInNewContext(code, { MACRO: macro }, { timeout: 30000 });
}

// 理專名字、樣式、同儕質疑等靜態資料，給實驗頁顯示
export function advisorMeta() {
  const code = shared.replace("/*TW*/", JSON.stringify({ asof: "", dates: [], stocks: [], etfs: [] }))
    .replace("/*PROFILES*/", profiles).replace("/*SHELF*/", shelf)
    + ";ADVISORS.map(a=>({key:a.key,name:a.name,emoji:a.emoji,tape:a.tape,horizon:a.horizon,school:a.school,bg:a.bg,style:a.style,critique:a.critique}))";
  return vm.runInNewContext(code, {});
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split("/").pop())) {
  const input = JSON.parse(readFileSync(0, "utf8"));
  const dates = input.dates.map(day => ({ date: day.date, results: runDate(day) }));
  process.stdout.write(JSON.stringify({ engine_sha: ENGINE_SHA, advisors: advisorMeta(), dates }));
}
