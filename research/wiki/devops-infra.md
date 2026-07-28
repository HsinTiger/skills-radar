# DevOps 基礎設施 (`devops-infra`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**338**（母體 6.25%）
- `PROVEN` production：**62.4%**（maturity 有效樣本 338）
- `PROVEN` agent target：**9.2%**（target 有效樣本 338）
- `PROVEN` 最新 evidence：2026-07-28 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 配置 (`configure`) | 42.1% |
| 調度 (`orchestrate`) | 21.1% |
| 驗證 (`verify`) | 13.1% |
| 分析 (`analyze`) | 9.2% |
| 生成 (`generate`) | 6.2% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 生成 (`generate`) | 21 / 74.0 | 0.28x |
| 轉換 (`transform`) | 9 / 26.9 | 0.33x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 338 | 6.25% | 62.4% | +0 | initial ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`6086cfe264b26a69955234000d532d1a842fbadf2db0d0cb0da7d4d4424c54cd`

[返回 Wiki index](README.md)
