# 理專圓桌（advisor-roundtable）

六位不同學經歷背景的 AI 理專，各用一套投資流派判斷股票進場時機，使用者以權重監督共識（human on the loop）。示範與研究用途，非投資建議。

- 網站：`web/index.html`（理專圓桌）與 `web/sim.html`（百萬模擬倉），由 `scripts/build_site.py` 從 `web/*.template.html` 產生
- 架構說明：見專案中的「理專圓桌 正式網站架構」文件

## 知識庫

| 檔案 | 內容 |
| --- | --- |
| `knowledge/sources.json` | 來源清單與授權。`ingest` 只收公有領域書與美國政府出版品；`read_only` 為不可放進 AI 的教材 |
| `knowledge/concepts.zh.json` | 每位理專 3 張自撰概念卡，對應延伸原典 |
| `scripts/build_knowledge.py` | 下載 Gutenberg 全文、去除檔頭、切段為 `knowledge/chunks/*.jsonl` |

```bash
python scripts/build_knowledge.py
```

授權提醒：OpenStax 教科書（CC BY-NC-SA）明文禁止未經書面許可用於大型語言模型，因此不納入。Gutenberg 書籍為美國公有領域，其他國家的著作權狀態請自行確認。

## 台股資料

| 檔案 | 內容 |
| --- | --- |
| `scripts/fetch_twse.py` | 從證交所 OpenAPI 與每日收盤行情抓資料，產生 `data/tw.json`（成交值超過 1 億元的上市普通股） |
| `scripts/build_site.py` | 把 `web/kb.js` 與 `data/tw.json` 嵌入 `web/index.template.html`，產生 `web/index.html` |

```bash
python scripts/fetch_twse.py && python scripts/build_site.py
```

目前內建資料是 2026-10-21 收盤快照。理專選股是固定規則的計算結果，不保證準確，也不是投資建議；要評估規則好不好，請用稽核紀錄或回測比對之後的實際股價。

## 理專內行筆記（2026-10-22 新增）

`knowledge/insider.zh.json` 收錄理專業內規範與實務常識，每條附官方出處：法規底線（金保法 KYC/KYP、公平待客、投顧法）、RR1–RR5、理專十誡、銀行公會疑似挪用態樣（網頁上可勾選自我檢查）、利益衝突、證照、台股常識（月營收、財報期限、注意/處置股）、同類網站比較，另含 5 題 KYC 示範測驗與自動計算的台股重要日期。`build_site.py` 會把它嵌入 `/*INSIDER*/`。法規如有修正請更新此檔並重新建置。

## ETF、理專背景與每日更新

- `data/tw.json` 的 `etfs` 收錄成交值超過 3000 萬元的上市 ETF，含類型與近一年配息；所有月收盤都已依除權息還原。
- `knowledge/advisors.zh.json` 是六位理專的背景檔案：經歷、在意的風險、評判標準、盲點、適合客群，以及 `fields`（每位理專只拿得到的資料欄位）。網頁會依 `fields` 把資料切給各理專，模擬不同背景的資訊差異。
- `.github/workflows/daily-update.yml` 每個交易日台灣時間 18:30 執行 `fetch_twse.py` 與 `build_site.py`，提交新資料並發佈到 GitHub Pages。啟用方式：repo 的 Settings → Pages → Source 選「GitHub Actions」。

## 上線必備設定（2026-10-23 新增）

`build_site.py` 產生 GitHub Pages 版時，會替每頁寫好完整的 `<head>`，內容依 `META` 表：

- 分頁標題（頁名｜理專圓桌）、搜尋摘要 `description`、`canonical`（以 GitHub Pages 網址為正本，避免和 Claude Artifact 版重複）
- 分享卡片：Open Graph 與 Twitter 卡片，圖片是 `web/og.png`（1200×630，原稿在 `scripts/brand/og.html`，用瀏覽器以 1200×630 截圖即可更新）
- 圖示：`web/favicon.svg`、`favicon-32.png`、`apple-touch-icon.png`
- 安全：`Content-Security-Policy` 與 `referrer` 用 meta 標籤（GitHub Pages 不能自訂回應標頭）
- 首頁加 `WebSite` 結構化資料
- 每頁加「跳到主要內容」連結與 `<main>` 地標

另外會產生 `web/404.html`（GitHub Pages 找不到網址時自動顯示）、`web/sitemap.xml` 與 `web/robots.txt`。專案網站的 robots.txt 不在網域根目錄，搜尋引擎不一定會讀；sitemap 請到 [Google Search Console](https://search.google.com/search-console) 手動提交。

選用的流量分析：到 [GoatCounter](https://www.goatcounter.com/) 註冊（不設 cookie，不需同意橫幅），把站台代碼填進 repo 的 Settings → Secrets and variables → Actions → Variables，名稱 `GOATCOUNTER_CODE`。設定後下一次每日更新就會啟用，CSP 與關於本站的隱私說明也會自動跟著改。
