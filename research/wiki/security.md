# 資安 (`security`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**288**（母體 5.17%）
- `PROVEN` production：**64.1%**（maturity 有效樣本 284）
- `PROVEN` agent target：**9.4%**（target 有效樣本 278）
- `PROVEN` 最新 evidence：2026-07-28 r2
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 驗證 (`verify`) | 59.5% |
| 分析 (`analyze`) | 15.8% |
| 配置 (`configure`) | 8.8% |
| 生成 (`generate`) | 5.6% |
| 檢索 (`retrieve`) | 5.3% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 調度 (`orchestrate`) | 6 / 44.1 | 0.14x |
| 生成 (`generate`) | 16 / 62.5 | 0.26x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 266 | 4.92% | 65.0% | +0 | initial ingest |
| 2026-07-28 | 2 | 288 | 5.17% | 64.1% | +168 | corpus recovery 1012 rows and editorial migration |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`3a2d07c6965d92c167a932ea1323b9bc9f77b921416afdc90a2363f1528133f6`

[返回 Wiki index](README.md)
