# 軟體開發 (`software-dev`)

> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。

## Owner notes

<!-- OWNER-NOTES:START -->
尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。
<!-- OWNER-NOTES:END -->

## Current evidence

- `PROVEN` 中立且可用的 domain 樣本：**2,064**（母體 33.66%）
- `PROVEN` production：**40.8%**（maturity 有效樣本 1,974）
- `PROVEN` agent target：**11.3%**（target 有效樣本 1,954）
- `PROVEN` 最新 evidence：2026-08-08 r1
- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。

### Task distribution

| task | share |
|---|---:|
| 生成 (`generate`) | 24.7% |
| 驗證 (`verify`) | 24.2% |
| 配置 (`configure`) | 18.6% |
| 調度 (`orchestrate`) | 10.6% |
| 分析 (`analyze`) | 9.4% |

### Structural signals

目前沒有符合訊號門檻的 task gap；這不等於 `PROVEN` 沒有機會。

## Evidence history

| date | rev | n | corpus share | production | total delta | note |
|---|---:|---:|---:|---:|---:|---|
| 2026-07-28 | 1 | 1,810 | 33.49% | 41.4% | +0 | initial ingest |
| 2026-07-28 | 2 | 1,849 | 33.18% | 41.2% | +168 | corpus recovery 1012 rows and editorial migration |
| 2026-07-29 | 1 | 1,864 | 33.16% | 41.1% | +48 | scheduled evidence ingest |
| 2026-08-08 | 1 | 2,064 | 33.66% | 40.8% | +510 | scheduled evidence ingest |

## Evidence contract

- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。
- 模型欄位信心門檻：`0.6`；各欄位分開判定。
- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。
- master SHA-256：`fb19ae1e48aaca91259bf08212990d203244d3699b28aab9a2406ce2630b9e99`

[返回 Wiki index](README.md)
