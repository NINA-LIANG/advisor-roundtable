# 分析計畫（事前登錄草稿，app 1.2.0）

這份文件是送 AsPredicted 或 OSF 事前登錄之前的草稿。正式收資料前請與指導教授確認，登錄後不要再改；之後若有偏離，在論文中逐項說明。

**狀態（2026-10-26）**：實驗暫停收資料（`config.json` 的 `paused: true`），實驗頁已從導覽列移除。論文第七版的研究範圍不含此實驗，倫理審查也還沒辦；是否納入論文、何時重新開放，待與指導教授確認。

1.2.0 依審查意見修正：第 4 組的依賴以調整前的等權建議為主要指標，另報告「把權重調向自己初判」的比例；操弄檢核失敗不再列入主要分析的排除條件（避免後處理偏誤），改為敏感度分析；Jian 量表正負向題分開報告並先檢查因素結構；新增「正確答案的限制」一節；「是否就讀或從事金融相關」拆成單選。

## 研究問題與假設

本研究比較四種呈現方式對「適度依賴」的影響：第 1 組單一理專、第 2 組只顯示六位理專的共識、第 3 組攤開六位理專的理由與分歧、第 4 組可自行調整採信權重。四組看到的最後建議都是同一個等權共識（第 4 組在調整權重之前），第 1、2 組附上同一份理由，因此第 1 與第 2 組的差異只來自來源標示（一位對六位），第 2 與第 3 組的差異來自是否揭露個別意見與分歧，第 3 與第 4 組的差異來自是否能調整權重。

H1：第 3 組在 AI 答錯的題目上推翻建議的機率高於第 2 組（過度依賴較低）。
H2：第 3 組在 AI 答對的題目上採納建議的機率不低於第 2 組（依賴不足沒有增加）。
H3：第 4 組的採納率高於第 3 組（Dietvorst et al., 2018 的「可修改就願意用」），但過度依賴不一定較低。第 4 組可以把權重調到讓建議和自己的初判一致，若以實際看到的建議計算採納，採納率會被機械性地墊高；因此 H3 以「調整權重之前的等權建議」為依賴對象檢定，並另外報告 `tuned_to_self`（初判與等權建議不同的題目中，調完權重後建議變成自己初判的比例），用來判斷第 4 組的「採納」有多少其實是把 AI 調成自己。
H4：第 1 與第 2 組的過度依賴沒有差異；若有差異，表示「六位共識」的標示本身會提高信任。

## 操作型定義

正確答案：決策月月底買進、持有 3 個月的報酬率勝過 0050 為「買進」，否則為「不買」；兩者差距小於 2 個百分點的題目不入題庫。這是事後結果，不代表事前可知，因此另做敏感度分析（見下）。

### 正確答案的限制

「三個月後是否勝過 0050」是事後結果。三個月的個股超額報酬很大一部分是事前無法預測的雜訊，受試者在 AI 答錯的題目上推翻建議，可能是判斷力，也可能只是運氣；適度依賴的概念則假設人在原則上有能力分辨 AI 何時是錯的。因此本實驗的依賴指標只能解釋為「在事後結果上的對錯」，論文須正面討論此限制，並以下方的敏感度分析 1 檢查結論是否只來自邊界題。另外，題庫依配額抽題（理專答對 11 題、答錯 5 題），AI 正確率固定為 68.75%，結論只能推論到準確率約七成的建議系統。

依賴指標以試題為單位：受試者第一次判斷（d1）與 AI 建議不同的試題，最後決定（d2）改成 AI 建議記為「採納」。RAIR 與 RSR 依 Schemmer et al. (2023) 定義，個人層級只作描述，因為每人的分母只有 3 到 6 題（`n_rair`、`n_rsr` 欄）。第 4 組另以實際看到的加權建議計算（`*_shown` 欄）。

## 主要分析

以 `trials.csv` 中「d1 與 AI 建議不同」的試題為樣本，依變項為是否採納（0/1），以廣義線性混合模型（logit 連結）估計：

```
adopt ~ cond * ai_correct + (1 + ai_correct | pid) + (1 + cond | item_id)
```

受試者與題目為交叉隨機效果（隨機效果結構依 Barr et al., 2013 從最大結構開始，無法收斂時依序移除隨機斜率並在論文中報告）。組別以 treatment coding、第 2 組為參照。H1 看 `cond3 × ai_correct=0`，H2 用等價檢定（TOST，界限為勝算比 0.8–1.25）。信心校準以 Brier 分數為依變項，以線性混合模型分析。

R 參考寫法：`lme4::glmer(adopt ~ cond * ai_correct + (1 + ai_correct | pid) + (1 + cond | item_id), family = binomial, data = d)`。

## 樣本數

題目只有 16 題，其中 AI 答錯 5 題，因此「題目」這一層的變異會大幅壓低檢定力（Westfall et al., 2014）。請在正式收資料前用前導測試的變異估計做模擬檢定力分析（例如 R 的 `simr` 套件），以 H1 的效果量（勝算比 1.8）、α = .05、檢定力 .80 求每組人數。在模擬結果出來之前，暫定每組 50 人、總計 200 人為下限。

## 排除標準（事前決定，不看結果）

以下任一情況排除整筆資料，並在論文報告各條件排除人數：兩題注意力檢核任一答錯；`prior_pids` 大於 0（同一瀏覽器之前用別的編號做過）；16 題中超過 4 題的第一次判斷少於 3 秒（`fast_trials`）；信任量表 12 題全部同一個數字（`straightline_trust`，量表內有反向題）；後測自述認出題目並寫出正確股名。

`site_before`＝「有」或 `site_trace`＝1 的受試者不排除，作為共變項，另做排除後的敏感度分析。

操弄檢核答錯（`manip_ok`＝0）不在主要分析中排除：操弄檢核在實驗處理之後才測量，各組答錯的機率可能因處理本身而不同（例如第 1、2 組只差一個來源標籤），依此排除會讓各組不再是隨機分派的可比群體（後處理偏誤；Aronow, Baron & Pinson, 2019，書目口試前請核對）。改為敏感度分析 5。

## 敏感度分析

1. 只保留超額報酬絕對值大於 5 個百分點的題目（`abs_excess`），檢查結論是否依賴勉強過門檻的題目。
2. 第 4 組改用 `rair_shown` 等以實際看到建議計算的指標。
3. 排除用過本站的受試者。
4. 加入金融素養、投資經驗、信任傾向（Merritt 六題平均）為共變項。
5. 排除操弄檢核答錯者後重跑主要分析，並報告各組答錯人數。

## 量表

信任：Jian et al. (2000) 12 題中譯，主要分數取前 11 題平均（第 12 題問熟悉度，另列）。前 5 題為負向題、第 6 至 11 題為正向題，已有研究指出兩組題目可能形成「不信任」與「信任」兩個因素，因此先以驗證性因素分析或至少分別計算兩組的 α 檢查結構，`participants.csv` 另列 `trust_neg_items` 與 `trust_pos_items`；若兩因素結構較佳，主要分析改用正向題平均。兩份量表的作答點數與錨點文字須對照原文確認，與原量表不同時在論文中說明。信任傾向：Merritt et al. (2013) 6 題中譯。兩份中譯在正式施測前需完成回譯（Brislin, 1970）並由第二位譯者比對；`scales.csv` 報告 Cronbach's α，α 低於 .70 時在論文中說明。

## 參考文獻

- Barr, D. J., Levy, R., Scheepers, C., & Tily, H. J. (2013). Random effects structure for confirmatory hypothesis testing: Keep it maximal. *Journal of Memory and Language, 68*(3), 255–278. https://doi.org/10.1016/j.jml.2012.11.001
- Brislin, R. W. (1970). Back-translation for cross-cultural research. *Journal of Cross-Cultural Psychology, 1*(3), 185–216. https://doi.org/10.1177/135910457000100301
- Dietvorst, B. J., Simmons, J. P., & Massey, C. (2018). Overcoming algorithm aversion: People will use imperfect algorithms if they can (even slightly) modify them. *Management Science, 64*(3), 1155–1170. https://doi.org/10.1287/mnsc.2016.2643
- Jian, J.-Y., Bisantz, A. M., & Drury, C. G. (2000). Foundations for an empirically determined scale of trust in automated systems. *International Journal of Cognitive Ergonomics, 4*(1), 53–71. https://doi.org/10.1207/S15327566IJCE0401_04
- Merritt, S. M., Heimbaugh, H., LaChapell, J., & Lee, D. (2013). I trust it, but I don't know why: Effects of implicit attitudes toward automation on trust in an automated system. *Human Factors, 55*(3), 520–534. https://doi.org/10.1177/0018720812465081
- Schemmer, M., Kuehl, N., Benz, C., Bartos, A., & Satzger, G. (2023). Appropriate reliance on AI advice: Conceptualization and the effect of explanations. In *Proceedings of the 28th International Conference on Intelligent User Interfaces* (pp. 410–422). https://doi.org/10.1145/3581641.3584066
- Westfall, J., Kenny, D. A., & Judd, C. M. (2014). Statistical power and optimal design in experiments in which samples of participants respond to samples of stimuli. *Journal of Experimental Psychology: General, 143*(5), 2020–2045. https://doi.org/10.1037/xge0000014
