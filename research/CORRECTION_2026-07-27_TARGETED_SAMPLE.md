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

## 解除 `BLOCKED` 的唯一條件

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
