# DevOps 基礎設施 (`devops-infra`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**453**（母體 7.26%）
- `PROVEN` production：**67.7%**（maturity 有效樣本 418）
- `PROVEN` agent target：**7.3%**（target 有效樣本 423）
- `PROVEN` 最新 evidence：2026-08-09 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 配置 (`configure`) | 45.0% |
| 調度 (`orchestrate`) | 20.6% |
| 驗證 (`verify`) | 12.5% |
| 分析 (`analyze`) | 9.1% |
| 生成 (`generate`) | 5.9% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 生成 (`generate`) | 24 / 90.5 | 0.27x |
| 轉換 (`transform`) | 9 / 31.3 | 0.29x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 338 | 6.25% | 62.4% | +0 | initial ingest |
| 2026-07-28 | 2 | 354 | 6.35% | 63.3% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 362 | 6.44% | 64.1% | +48 | scheduled evidence ingest |
| 2026-08-08 | 1 | 439 | 7.16% | 67.2% | +510 | scheduled evidence ingest |
| 2026-08-09 | 1 | 453 | 7.26% | 67.7% | +111 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`525eae0729c04016805952d540523f4d663494c1d9fd93dad59b9b4b9096eed1`

[返回 Wiki index](README.md)
