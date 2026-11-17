# 論文實驗用資料夾（CR-016）

論文：《資料治理機制對生成式人工智慧知識查詢之正確性與資料隔離之影響－以「理專圓桌」知識庫為例》（草稿，題目待指導教授確認）。

這個資料夾只放**格式與範例**，不屬於實驗文件庫（`scripts/export_corpus.py` 不會把它放進去）。

| 檔案 | 用途 |
|---|---|
| `題庫/題庫範本.csv` | 題庫欄位與 7 題範例（取自論文表 3-5）。正式題庫由研究者擬定，放在電腦的 `kb-private/` 或 `experiment-private/`，事先登錄前不公開 |
| `受限文件格式.md` | 研究用虛構受限文件的格式（六個分區的內部工作筆記、管理者稽核紀錄），實際檔案放 `kb-private/`，不進 git |

相關程式：

```bash
python scripts/build_catalog.py                  # 重建文件庫目錄 knowledge/governance/catalog.json
python scripts/validate_qbank.py 題庫.csv         # 檢查題庫
python scripts/kb_gate.py --role external --list # 外部使用者看得到哪些段落
python scripts/export_corpus.py --out 某資料夾     # 凍結文件庫：匯出三個條件的文件庫與 SHA-256 清單
```

三個條件的內容完全相同：條件一是原始檔案拿掉代號、不附詮釋資料；條件二、三是附詮釋資料的知識單元，條件三另外在檢索前依角色過濾、回答後過出處驗證閘門。
