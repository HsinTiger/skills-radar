# 寫作內容 (`writing-content`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**175**（母體 3.11%）
- `PROVEN` production：**28.5%**（maturity 有效樣本 172）
- `PROVEN` agent target：**1.7%**（target 有效樣本 172）
- `PROVEN` 最新 evidence：2026-07-29 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 生成 (`generate`) | 41.4% |
| 轉換 (`transform`) | 36.7% |
| 驗證 (`verify`) | 7.1% |
| 檢索 (`retrieve`) | 5.3% |
| 分析 (`analyze`) | 3.6% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 配置 (`configure`) | 5 / 28.6 | 0.17x |
| 調度 (`orchestrate`) | 5 / 26.2 | 0.19x |
| 分析 (`analyze`) | 6 / 21.1 | 0.28x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 166 | 3.07% | 29.5% | +0 | initial ingest |
| 2026-07-28 | 2 | 173 | 3.10% | 28.7% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 175 | 3.11% | 28.5% | +48 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`aa0fb3da6ba9ec1e7b85aaea3a73aed1dcd5872e598e60160abc981af2028f75`

[返回 Wiki index](README.md)
