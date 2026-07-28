# 2026-07-27 過取樣污染修正

## 結論

`research/insights/2026-07-27.md` 的母體統計已標為 `SUPERSEDED`，不可引用。
產生它的程式只排除 `targeted-eda`，沒有排除後來新增的 `targeted-wifi` 與
`targeted-eda2`，違反中立樣本／過取樣樣本分離的不變量。

## Claim / Evidence / Risk

| 狀態 | Claim | Evidence | Risk |
|---|---|---|---|
| `PROVEN` | 舊 `n_total=24,944` 含過取樣污染 | Release snapshot 共 41,230 筆；`targeted-eda=16,286`、`targeted-wifi=10,832`、`targeted-eda2=8,682`。41,230 − 16,286 = 24,944，證明舊程式只排除第一類 | 舊報告的領域比例、上線率、task gap 與趨勢不可用 |
| `PROVEN` | Release snapshot 的中立樣本為 5,430 筆；套 domain confidence 門檻後為 5,405 筆 | `sample` 缺值／neutral 且 domain 可用的確定性重算 | 僅代表該 Release snapshot |
| `PROVEN` | 該 snapshot 重算的全體 production 為 42.3%，verify 為 15.0% | `bin/opportunity.py` 套共用 sample policy 與 field confidence 後的本機輸出 | 不得和 48.4%／18.4% 混用 |
| `BLOCKED` | 尚不能重建最新 production 頁面 | Release master 只有 5,937 個非 model 種子；repo `corpus/model_report.json` 記錄 6,547 個種子，差 610 筆 | 用 Release 重建會讓 EDA 內部分析由 1,359 件退回 stale 結果 |

## 修復

1. 所有統計 consumer 改用 `bin/corpus_policy.py`；只接受缺值、空值或 `neutral`，
   所有 `targeted-*` 一律排除於母體估計。
2. model 標籤依分析欄位分別套 `*_conf >= 0.6`。
3. 加入 master／`model_report.json` 對齊檢查；stale Release 不再能產生假的 PASS。
4. Wiki ingest 同日證據變動必須附 revision note，且永不複製第三方原文。

## 當時解除 `BLOCKED` 的條件（歷史紀錄）

由 canonical runtime 重新發佈含 6,547 seeds／34,683 model predictions 的
`master.jsonl`（或更新 Release asset），核對 SHA-256 後依序執行：

```text
python3 bin/opportunity.py
python3 bin/eda_deepdive.py
python3 bin/wiki_ingest.py --date 2026-07-27 --revision-note "sample-policy correction"
python3 bin/build_site.py
python3 bin/wiki_lint.py
python3 bin/check_privacy.py
```

## 2026-07-28 Resolution

- `PROVEN`：原 610 筆 Mac LLM batch 未存在 Git 或 Release，不能冒充還原。
- `PROVEN`：以 640 筆平衡 recovery sample（`targeted-eda2`／`targeted-wifi` 各半、八個 topic tier 等量）重新做完整 LLM 標註；每個 index 唯一且 enum 合法後才合併。
- `PROVEN`：新 recoverable baseline 為 41,230 rows、6,577 seeds、34,653 model predictions；master SHA-256 `6086cfe264b26a69955234000d532d1a842fbadf2db0d0cb0da7d4d4424c54cd`。
- `PROVEN`：rolling Release `corpus-latest` asset SHA-256 `6727d6ced0055ab13ea15c444873274c5331b20283a06f2fcb44c0273510fb00` 已 readback。
- `PROVEN`：neutral-only Wiki 與首頁已重建；舊受污染報告保留 `SUPERSEDED`，不改寫歷史。

這個 resolution 不表示 skill 正確、已安裝、已上線、EDA signoff 或投資成效；它只解除 corpus freshness 與資料可恢復性阻塞。
