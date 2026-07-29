# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-07-29](daily/2026-07-29.md)

**今日一句話**：官方數據因資料收集階段未安裝 `gh` CLI 而無變更紀錄；社群與學術界高度集中於「Agent 上下文污染隔離（Taint Confinement）」與「Claude Code 本地 Session 記憶 / 隱私防護工具」。

**短期建議（一週內）**

1. **Pipeline 前置防護關卡建置**：檢視 Substack、IC/WiFi 知識庫發布流程。在外呼 Claude Code 或大模型前，導入本機端語法/Regex 檢查層（參考 `Hamza` 思維），確保內網暫存檔、API key 與未公開 baseband spec 在 request 送出前強制遮蔽。
2. **評估 Sessiongrep 本地記憶機制**：
   - **目標**：解決多條 Pipeline 與 CLI 輪替作業時的 context 檢索斷層。
   - **驗證步驟**：
     1. `git clone https://github.com/braincompany/sessiongrep` 至本地 scratch 目錄。
     2. 檢查原始碼是否包含任何外連 HTTP 請求或遙測（telemetry）程式碼。
     3. 確認資料僅寫入本地 SQLite/Vector DB 後，先以測試 Session 驗證讀寫效能與穩定度。

## 生態指標

| repo | 目前 star | 自 2026-07-26 起變化 |
|---|---:|---:|

## 這個系統怎麼運作

```
bin/fetch.py        抓事實（GitHub API / arXiv / HN），不做判斷
                    → 第三方文字一律標記 _untrusted，供下游模型辨識
index/prompt_daily.txt  分析規格（含 prompt injection 防禦指令）
bin/run_daily.sh    主流程：抓取 → agy 產簡報 → 驗收 → 更新 README → push
bin/build_readme.py 重建本頁
data/snapshot.json  上次狀態（用於 diff 出「今天有什麼變了」）
data/history.jsonl  指標時序
daily/YYYY-MM-DD.md 每日簡報
```

排程：launchd `com.hsin.skills-radar`，每日 08:30 執行。
手動跑一次：`~/skills-radar/bin/run_daily.sh`

## 歷史簡報

- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
