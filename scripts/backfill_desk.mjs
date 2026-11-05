// CR-011 理專辦公室補記：用 data-history 分支保存的每日快照，從最早一天開始逐日重跑理專辦公室，
// 補上上線（2026-11-05）以前的工作日誌、對話與六人帳戶。需求者 2026-11-05 要求補 10/22 起的紀錄。
//
// 每一天只用「那一天的快照」：理專看到的資料、做的決定，和那天實際跑會得到的一樣，沒有用到之後的資料。
// 快照有缺的日子（每日更新沒跑成的交易日）沒有收盤資料，就不寫日誌；前一個快照日做的決定，
// 在下一個有快照的交易日用那天的收盤價成交，頁面會標出缺漏。
// 補記的日誌都標 backfill，頁面顯示「補記」，第一段說明是事後依當天資料補寫的。
//
// 用法：node scripts/backfill_desk.mjs <快照資料夾>
//   快照資料夾放 YYYY-MM-DD.json（各日的 tw.json），例如從 data-history 分支解壓出來
// 輸出：覆寫 data/desk.json、data/advisor_books.json（會從頭重算，請只在還沒有正式紀錄、或確定要重來時使用）
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { buildDay, bannedIn } from "./advisor_desk.mjs";

const ROOT = new URL("..", import.meta.url);
const cfg = JSON.parse(readFileSync(new URL("knowledge/action_log.zh.json", ROOT), "utf8"));

export function backfill(snaps, morning = { days: [] }, today = null) {
  let desk = { days: [] }, books = null;
  const dates = snaps.map(t => t.asof);
  for (const tw of snaps) {
    const checksDay = morning.days.find(d => d.asof === tw.asof) || null;
    const r = buildDay(tw, desk, books, checksDay);
    const day = r.day;
    if (tw.asof !== today) {
      day.backfill = true;
      for (const j of Object.values(day.journals))
        j.lines.seen.unshift({ t: `（補記：這篇是 ${today || "事後"} 依 ${tw.asof} 當天保存的資料補寫的，內容和那天實際執行會得到的相同。）`, c: [] });
    }
    desk = { days: [day, ...desk.days].slice(0, cfg.keep_days) };
    books = r.books;
  }
  books.backfill = { from: dates[0], to: today, dates };
  return { desk: { asof: dates.at(-1), keep_days: cfg.keep_days, days: desk.days }, books };
}

function main() {
  const dir = process.argv[2];
  if (!dir) { console.error("用法：node scripts/backfill_desk.mjs <快照資料夾>"); process.exit(2); }
  const files = readdirSync(dir).filter(f => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort();
  const snaps = files.map(f => JSON.parse(readFileSync(`${dir}/${f}`, "utf8")));
  snaps.forEach((t, i) => { if (t.asof !== files[i].slice(0, 10)) throw new Error(`${files[i]} 的資料日是 ${t.asof}`); });
  const mp = new URL("data/morning_report.json", ROOT);
  const morning = existsSync(mp) ? JSON.parse(readFileSync(mp, "utf8")) : { days: [] };
  const today = JSON.parse(readFileSync(new URL("data/tw.json", ROOT), "utf8")).asof;
  const { desk, books } = backfill(snaps, morning, today);
  const hit = desk.days.flatMap(d => bannedIn(d));
  if (hit.length) { console.error(`出現禁語：${hit.join("、")}`); process.exit(1); }
  writeFileSync(new URL("data/desk.json", ROOT), JSON.stringify(desk));
  writeFileSync(new URL("data/advisor_books.json", ROOT), JSON.stringify(books));
  for (const k in books.nav) console.log(k, books.nav[k].map(([d, v]) => `${d.slice(5)} ${Math.round(v).toLocaleString()}`).join("｜"));
  console.log(`ok  補記 ${snaps.length} 個交易日：${snaps.map(t => t.asof).join("、")}`);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].split("/").pop())) main();
