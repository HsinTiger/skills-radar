# 營運行政 (`ops-admin`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**261**（母體 4.26%）
- `PROVEN` production：**39.3%**（maturity 有效樣本 257）
- `PROVEN` agent target：**7.0%**（target 有效樣本 257）
- `PROVEN` 最新 evidence：2026-08-08 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 調度 (`orchestrate`) | 30.4% |
| 檢索 (`retrieve`) | 15.6% |
| 分析 (`analyze`) | 14.8% |
| 配置 (`configure`) | 12.8% |
| 生成 (`generate`) | 12.0% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 驗證 (`verify`) | 11 / 40.2 | 0.27x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 248 | 4.59% | 39.9% | +0 | initial ingest |
| 2026-07-28 | 2 | 255 | 4.58% | 39.0% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 258 | 4.59% | 39.5% | +48 | scheduled evidence ingest |
| 2026-08-08 | 1 | 261 | 4.26% | 39.3% | +510 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`fb19ae1e48aaca91259bf08212990d203244d3699b28aab9a2406ce2630b9e99`

[返回 Wiki index](README.md)
