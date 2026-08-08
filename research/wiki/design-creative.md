# 設計創意 (`design-creative`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**338**（母體 6.01%）
- `PROVEN` production：**37.8%**（maturity 有效樣本 333）
- `PROVEN` agent target：**7.3%**（target 有效樣本 329）
- `PROVEN` 最新 evidence：2026-07-29 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 生成 (`generate`) | 65.8% |
| 轉換 (`transform`) | 15.2% |
| 驗證 (`verify`) | 5.7% |
| 檢索 (`retrieve`) | 4.5% |
| 調度 (`orchestrate`) | 3.9% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 分析 (`analyze`) | 7 / 42.0 | 0.17x |
| 配置 (`configure`) | 10 / 56.9 | 0.18x |
| 調度 (`orchestrate`) | 13 / 52.0 | 0.25x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 324 | 5.99% | 38.0% | +0 | initial ingest |
| 2026-07-28 | 2 | 335 | 6.01% | 38.0% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 338 | 6.01% | 37.8% | +48 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`aa0fb3da6ba9ec1e7b85aaea3a73aed1dcd5872e598e60160abc981af2028f75`

[返回 Wiki index](README.md)
