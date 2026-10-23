# 歷史總經資料（給總經派理專）

`macro_2023_2024.csv` 每列是「資料所屬月份」的數值。決策日是某月最後一個交易日時，
只用**那時已經公布**的資料：景氣燈號約在次月 27 日公布、PMI 約在次月第一個工作日公布，
所以 2024-03 的決策日用的是 2024-02 的燈號與 PMI（`build_experiment_items.py` 會自動往前錯一個月）。

| 欄位 | 內容 | 狀態 |
| --- | --- | --- |
| `light` | 國發會景氣對策信號燈號 | 2023-09 起依[金融情報站整理的國發會紀錄](https://fininfostation.com/climate)；2023-06～08 依新聞「連 9 藍」「連 10 藍」（[科技新報 2023-08-28](https://finance.technews.tw/2023/08/28/the-economic-indicators-showed-signs-of-bottoming-out-in-july/)、[2023-09-27](https://finance.technews.tw/2023/09/27/august-prosperity-lights/)）。正式使用前請到[國發會景氣指標查詢系統](https://index.ndc.gov.tw/)核對一次 |
| `score` | 綜合判斷分數（只供參考，理專不使用） | 同上；2023-06～08 待補 |
| `pmi` | 國發會／中經院台灣製造業採購經理人指數 | **待補**：請依[國發會 PMI 新聞稿](https://www.ndc.gov.tw/)逐月填入。空白時總經派會略過 PMI 這一項，題庫會標成草稿 |

央行利率方向：2023-03-23 與 2024-03-21 各升息半碼，之後到 2024 年底都沒有降息，
所以 18 個決策日都記為「升息循環」（`rate = 1`，規則是過去 12 個月內有升息）。這個判斷寫在 `build_experiment_items.py` 的 `RATE_HIKES`。
