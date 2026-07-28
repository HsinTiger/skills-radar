# 行銷成長 (`marketing-growth`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**203**（母體 3.76%）
- `PROVEN` production：**35.5%**（maturity 有效樣本 203）
- `PROVEN` agent target：**2.5%**（target 有效樣本 202）
- `PROVEN` 最新 evidence：2026-07-28 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 生成 (`generate`) | 36.9% |
| 分析 (`analyze`) | 27.1% |
| 調度 (`orchestrate`) | 18.2% |
| 驗證 (`verify`) | 4.9% |
| 檢索 (`retrieve`) | 4.9% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 配置 (`configure`) | 9 / 34.6 | 0.26x |
| 驗證 (`verify`) | 10 / 30.5 | 0.33x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 203 | 3.76% | 35.5% | +0 | initial ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`6086cfe264b26a69955234000d532d1a842fbadf2db0d0cb0da7d4d4424c54cd`

[返回 Wiki index](README.md)
