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

## 後台與資料管線（2026-10-23 新增）

網站維持「靜態網站＋GitHub Actions」：不用租主機、沒有資料庫要顧。GitHub 本身就是後台。

| 想做的事 | 怎麼做 |
| --- | --- |
| 看今天資料有沒有更新成功 | 網站的「資料狀態」頁 `status.html`（每份資料的日期、筆數、狀態） |
| 立刻重抓資料 | Actions → daily-update → Run workflow，可選只更新某一份；手動執行不看休市日 |
| 改理專背景等內容 | 直接在 GitHub 網頁改 `knowledge/*.json`，或登入 [Pages CMS](https://app.pagescms.org/) 用表單改（設定在 `.pages.yml`，目前開放六位理專背景） |
| 出問題時收到通知 | 任何一步失敗會自動開一張 `data-update` 標籤的 Issue（GitHub 會寄信），之後成功一次自動關閉 |
| 拿資料做研究 | 網站上的 `data/*.json`（與網頁同一份），每天的歷史快照在 `data-history` 分支 |

每日更新的流程（`.github/workflows/daily-update.yml`）：

1. `scripts/market_open.py`：查證交所休市表，休市日跳過（抓不到休市表就照跑）
2. 五支 `scripts/fetch_*.py`：網路請求都經過 `scripts/net.py`，連不上會等 2、4、8 秒重試；任何一支失敗只沿用舊資料，不中斷
3. `scripts/validate_data.py`：發佈前的品質關卡。格式壞、筆數太少、價格不合理、知識庫欄位缺漏 → 這次不提交、不發佈，網站繼續顯示上一份好資料；只是資料太舊或某支抓取失敗 → 照常發佈並開 Issue。結果寫到 `data/status.json`
4. `scripts/build_site.py`：重建網頁、產生資料狀態頁，並把資料複製到 `web/data/` 一起發佈
5. `scripts/snapshot_history.py`：把當天資料壓縮存到 `data-history` 分支的 `YYYY/MM/YYYY-MM-DD/`，主分支不會越來越大
6. `scripts/run_report.py`：整理各步驟成敗，開或關 Issue

PR 與推到 main 時，`.github/workflows/ci.yml` 會跑 `tests/` 的單元測試、資料檢查與建置。本機執行：

```bash
pip install pytest && python -m pytest -q
python scripts/validate_data.py --status data/status.json && python scripts/build_site.py
```

## 論文使用者實驗（2026-10-23 新增）

四組受試者間實驗：1 單一理專、2 只顯示共識、3 完整圓桌（分歧與理由）、4 自己調權重。實驗頁 `study.html` 不在導覽列與 sitemap 裡、不給搜尋引擎收錄，只透過研究者發的連結進入。

| 檔案 | 內容 |
| --- | --- |
| `scripts/fetch_experiment_panel.py` | 抓 2022-07～2025-03 證交所歷史資料 → `knowledge/experiment/panel.json`（只抓一次） |
| `scripts/advisor_engine.mjs` | 在 Node 裡跑首頁同一份六位理專規則（直接從 `web/index.template.html` 切出來執行） |
| `scripts/build_experiment_items.py` | 算正確答案（3 個月報酬是否勝過 0050）、分層抽 16＋2 題、遮蔽股名日期 → `items.v1.json`（實驗頁用）、`key.v1.json`（答案）、`manifest.json`（SHA-256） |
| `knowledge/experiment/macro_2023_2024.csv` | 景氣燈號、PMI（說明與出處見 `macro_README.md`） |
| `knowledge/experiment/config.json` | 抽題設定（種子、名額）與研究資訊（同意書欄位、DataPipe 實驗代號） |
| `knowledge/experiment/surveys.zh.json` | 前測、後測題目（金融素養、信任量表、操弄檢核、注意力檢核） |
| `web/study.template.html` | 實驗流程與四組畫面 |
| `scripts/make_assignments.py` | 產生受試者編號與連結（置換區塊隨機化，組別由編號算出） |
| `analysis/score_study.py` | 合併 DataPipe 資料，算 RAIR、RSR、過度依賴、正確率、Brier、信任等指標 |
| `.github/workflows/build-experiment.yml` | 在 GitHub Actions 抓資料並建題庫（這個開發環境連不到證交所） |

上線前要做的事：

1. **題庫**：推送後 build-experiment 會自動跑（約 25 分鐘）並把題庫提交回分支。PMI 還沒補齊時題庫是草稿（`draft: true`），補完 `macro_2023_2024.csv` 再跑一次就是正式版，之後不會再被覆寫。
2. **DataPipe**：到 [pipe.jspsych.org](https://pipe.jspsych.org/) 註冊、連 Google 雲端硬碟、建一個實驗並開啟資料收集，把實驗代號填進 `config.json` 的 `datapipe_experiment_id`。公開招募想讓 DataPipe 輪流分組，就在後台開「condition assignment」設 4 組，並把 `datapipe_condition_assignment` 改成 `true`。送資料的網址寫在 `study.template.html` 的 `send()`，請和 DataPipe 後台 Code Samples 對一次。沒設定時，受試者在最後可以下載作答檔交給你。
3. **同意書**：聯絡信箱、謝禮在 `config.json`；之後要送倫理審查的話，加上 `rec_approval`（審查編號）與 `rec_contact` 就會出現在同意書；同意書文字在 `study.template.html` 的 `consent()`。
4. **預覽**：`study.html?preview=1&cond=1`（1～4 組），預覽不會送資料。
5. **發連結**：`python scripts/make_assignments.py 120 > experiment-private/pids.csv`，依報名順序發。`experiment-private/` 不會提交。
6. **分析**：從雲端硬碟下載 `DataPipe` 資料夾，`python analysis/score_study.py 下載的資料夾` → `experiment-private/trials.csv`、`participants.csv`。

注意：repo 是公開的，`key.v1.json` 裡有答案。實驗頁本身不嵌入正式題答案，結束時才讀 `study-key.json` 揭曉；但有心人仍可從 repo 找到答案，按答對題數發獎金時請把這點寫進論文的限制。
