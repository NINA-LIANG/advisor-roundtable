// 上線後冒煙測試：網站發佈之後，用真的瀏覽器把每一頁打開一次，確認「使用者實際看到的網站」沒有壞掉。
// CI 檢查的是程式碼；這支檢查的是發佈出去的結果（部署失敗、快取沒更新、某頁 JS 錯誤整頁空白，CI 都看不到）。
//
// 用法：node scripts/smoke_live.mjs [網址] [--asof YYYY-MM-DD]
//   網址預設為正式站；--asof 預設讀 data/tw.json 的 asof（確認線上的資料日期和 main 分支一致）
//   結果寫到 smoke_report.md；有任何一項沒過，結束碼為 1
//
// 每一頁檢查（手機 390px 與電腦 1280px 各一次）：
//   1. 打得開（HTTP 200）  2. 沒有 JS 錯誤  3. 有分頁標題  4. 有免責聲明「非投資建議」  5. 手機寬度沒有橫向跑版
// 首頁另外檢查：6. 線上資料日期和 main 分支一致  7. 六位理專的卡片或 KYC 說明有顯示出來（不是空白）
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

// 用 require 載入，雲端與本機的全域安裝（NODE_PATH）都找得到
const { chromium } = createRequire(import.meta.url)("playwright");

const ROOT = new URL("..", import.meta.url);
const args = process.argv.slice(2);
const base = (args.find(a => a.startsWith("http")) || "https://nina-liang.github.io/advisor-roundtable/").replace(/\/?$/, "/");
const i = args.indexOf("--asof");
const asof = i >= 0 ? args[i + 1] : JSON.parse(readFileSync(new URL("data/tw.json", ROOT), "utf8")).asof;

// 頁面清單取自 sitemap.xml，新增頁面時會自動納入
const pages = [...readFileSync(new URL("web/sitemap.xml", ROOT), "utf8").matchAll(/<loc>[^<]*\/([^/<]*)<\/loc>/g)]
  .map(m => m[1] || "index.html");

const rows = [];
const fail = (page, view, what) => rows.push({ page, view, what });

const browser = await chromium.launch();
for (const [view, width] of [["手機", 390], ["電腦", 1280]]) {
  const ctx = await browser.newContext({ viewport: { width, height: 800 } });
  for (const p of pages) {
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    let res;
    try {
      res = await page.goto(base + (p === "index.html" ? "" : p) + `?smoke=${Date.now()}`, { waitUntil: "load", timeout: 60000 });
    } catch (e) {
      fail(p, view, `打不開：${e.message.split("\n")[0]}`);
      await page.close();
      continue;
    }
    if (!res || res.status() !== 200) fail(p, view, `HTTP ${res ? res.status() : "無回應"}`);
    await page.waitForTimeout(1500);
    for (const e of errors) fail(p, view, `JS 錯誤：${e.slice(0, 120)}`);
    if (!(await page.title()).trim()) fail(p, view, "沒有分頁標題");
    const html = await page.content();
    if (!html.includes("非投資建議")) fail(p, view, "找不到免責聲明「非投資建議」");
    if (width === 390) {
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 1) fail(p, view, `橫向跑版（多出 ${over}px）`);
    }
    if (p === "index.html") {
      if (!html.includes(`"asof":"${asof}"`)) {
        const live = (html.match(/"asof":"([\d-]+)"/) || [])[1] || "找不到";
        fail(p, view, `線上資料日期 ${live}，main 分支是 ${asof}（可能還沒發佈或快取未更新）`);
      }
      const cards = await page.evaluate(() => (document.getElementById("cards")?.innerText || "").trim().length);
      if (!cards) fail(p, view, "理專卡片區是空白的");
    }
    await page.close();
  }
  await ctx.close();
}
await browser.close();

const total = pages.length * 2;
const bad = new Set(rows.map(r => r.page + r.view)).size;
const lines = [
  `## 上線後冒煙測試 ${rows.length ? "❌ 有問題" : "✅ 全部通過"}`,
  "",
  `網址：${base}　資料日期應為：${asof}　檢查頁數：${pages.length} 頁 × 手機／電腦 = ${total} 次，有問題 ${bad} 次`,
  "",
];
if (rows.length) {
  lines.push("| 頁面 | 寬度 | 問題 |", "|---|---|---|", ...rows.map(r => `| ${r.page} | ${r.view} | ${r.what.replace(/\|/g, "／")} |`));
} else {
  lines.push("每一頁都打得開、沒有 JS 錯誤、有標題與免責聲明、手機不跑版；首頁資料日期正確，理專卡片有顯示。");
}
writeFileSync("smoke_report.md", lines.join("\n") + "\n");
console.log(lines.join("\n"));
process.exit(rows.length ? 1 : 0);
