# 資安 (`security`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**343**（母體 5.59%）
- `PROVEN` production：**66.9%**（maturity 有效樣本 329）
- `PROVEN` agent target：**8.2%**（target 有效樣本 316）
- `PROVEN` 最新 evidence：2026-08-08 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 驗證 (`verify`) | 61.9% |
| 分析 (`analyze`) | 15.9% |
| 配置 (`configure`) | 7.8% |
| 檢索 (`retrieve`) | 5.0% |
| 生成 (`generate`) | 5.0% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 調度 (`orchestrate`) | 6 / 48.5 | 0.12x |
| 生成 (`generate`) | 16 / 70.5 | 0.23x |
| 轉換 (`transform`) | 8 / 25.0 | 0.32x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 266 | 4.92% | 65.0% | +0 | initial ingest |
| 2026-07-28 | 2 | 288 | 5.17% | 64.1% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 292 | 5.19% | 64.1% | +48 | scheduled evidence ingest |
| 2026-08-08 | 1 | 343 | 5.59% | 66.9% | +510 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`fb19ae1e48aaca91259bf08212990d203244d3699b28aab9a2406ce2630b9e99`

[返回 Wiki index](README.md)
