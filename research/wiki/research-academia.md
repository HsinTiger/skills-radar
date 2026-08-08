# 研究學術 (`research-academia`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**203**（母體 3.61%）
- `PROVEN` production：**26.9%**（maturity 有效樣本 201）
- `PROVEN` agent target：**5.2%**（target 有效樣本 194）
- `PROVEN` 最新 evidence：2026-07-29 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 分析 (`analyze`) | 27.0% |
| 檢索 (`retrieve`) | 20.6% |
| 生成 (`generate`) | 18.5% |
| 轉換 (`transform`) | 10.1% |
| 調度 (`orchestrate`) | 9.5% |

### Structural signals

| missing task | observed / expected | ratio |
|---|---:|---:|
| 配置 (`configure`) | 11 / 32.0 | 0.34x |

`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 188 | 3.48% | 27.1% | +0 | initial ingest |
| 2026-07-28 | 2 | 203 | 3.64% | 26.9% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 203 | 3.61% | 26.9% | +48 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`aa0fb3da6ba9ec1e7b85aaea3a73aed1dcd5872e598e60160abc981af2028f75`

[返回 Wiki index](README.md)
