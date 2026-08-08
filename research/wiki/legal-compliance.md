# 法務合規 (`legal-compliance`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**107**（母體 1.75%）
- `PROVEN` production：**65.0%**（maturity 有效樣本 100）
- `PROVEN` agent target：**1.0%**（target 有效樣本 101）
- `PROVEN` 最新 evidence：2026-08-08 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 驗證 (`verify`) | 34.8% |
| 生成 (`generate`) | 25.0% |
| 分析 (`analyze`) | 16.3% |
| 檢索 (`retrieve`) | 9.8% |
| 轉換 (`transform`) | 6.5% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 調度 (`orchestrate`) | 2 / 13.9 | 0.14x |
| 配置 (`configure`) | 5 / 15.5 | 0.32x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 88 | 1.63% | 63.6% | +0 | initial ingest |
| 2026-07-28 | 2 | 93 | 1.67% | 64.8% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 95 | 1.69% | 65.6% | +48 | scheduled evidence ingest |
| 2026-08-08 | 1 | 107 | 1.75% | 65.0% | +510 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`fb19ae1e48aaca91259bf08212990d203244d3699b28aab9a2406ce2630b9e99`

[返回 Wiki index](README.md)
