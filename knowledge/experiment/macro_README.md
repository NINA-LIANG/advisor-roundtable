# 歷史總經資料（給總經派理專）

`macro_2023_2024.csv` 每列是「資料所屬月份」的數值。決策日是某月最後一個交易日時，
只用**那時已經公布**的資料：景氣燈號約在次月 27 日公布、PMI 約在次月第一個工作日公布，
所以 2024-03 的決策日用的是 2024-02 的燈號與 PMI（`build_experiment_items.py` 會自動往前錯一個月）。

| 欄位 | 內容 | 狀態 |
| --- | --- | --- |
| `light` | 國發會景氣對策信號燈號 | 2023-09 起依[金融情報站整理的國發會紀錄](https://fininfostation.com/climate)；2023-06～08 依新聞「連 9 藍」「連 10 藍」（[科技新報 2023-08-28](https://finance.technews.tw/2023/08/28/the-economic-indicators-showed-signs-of-bottoming-out-in-july/)、[2023-09-27](https://finance.technews.tw/2023/09/27/august-prosperity-lights/)）。正式使用前請到[國發會景氣指標查詢系統](https://index.ndc.gov.tw/)核對一次 |
| `score` | 綜合判斷分數（只供參考，理專不使用） | 同上；2023-06～08 待補 |
| `pmi` | 中經院台灣製造業採購經理人指數（季節調整後） | 2026-10-23 依[中經院每月新聞稿](https://www.cier.edu.tw/eco/2024%e5%b9%b43%e6%9c%88%e5%8f%b0%e7%81%a3%e8%a3%bd%e9%80%a0%e6%a5%ad%e6%8e%a1%e8%b3%bc%e7%b6%93%e7%90%86%e4%ba%ba%e6%8c%87%e6%95%b8/)填入，每個月都用新聞稿寫的「升／跌 X 個百分點」和前一個月互相核對過；2023-06、2023-07 與 2024-10、2024-11 來自轉載新聞稿的報導（[科技新報 2023-07-04](https://finance.technews.tw/2023/07/04/pmi-june/)、[2023-08-02](https://technews.tw/2023/08/02/pmi-july/)、[鉅亨網](https://news.cnyes.com/news/id/5761225)、[中央社 2024-12-02](https://www.cna.com.tw/news/afe/202412020266.aspx)） |

央行利率方向：2023-03-23 與 2024-03-21 各升息半碼，之後到 2024 年底都沒有降息，
所以 18 個決策日都記為「升息循環」（`rate = 1`，規則是過去 12 個月內有升息）。這個判斷寫在 `build_experiment_items.py` 的 `RATE_HIKES`。
