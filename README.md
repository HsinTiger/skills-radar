# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-08-03](daily/2026-08-03.md)

**今日一句話**：學術界證實「純自然語言 Markdown Skills」的邏輯違約率高達 44%，生態前沿正劇烈從「鬆散散文 SOP（Prose Skills）」轉向「強型別、可編譯、確定性的線束套件（Typed Harnesses）」。

**短期建議（一週內）**

1. **立即修復背景情報自動抓取機器的 `PATH`**
   今日的報錯表明你執行 Python 爬蟲腳本的環境（如 crontab 或後台 task）無法識別 `gh`（GitHub CLI）。在腳本內改用環境變數全路徑（如 `/opt/homebrew/bin/gh` 或 `/usr/local/bin/gh`），否則每日的生態觀測將大片失明。
2. **限縮 Claude Code 與本地 CLI 的默認綁定行為**
   檢查現有的 Claude Code 與 agy 配置檔。若你有開關能控制「打開檔案夾預設上傳（Attach Open File by Default）」，務必**設為強制停用**，只保留由顯式參數（Explicit Pass-in）或自訂指令遞送的精確 Context。在 Baseband 工作區中更嚴格落實，防止不意間將 IC Draft 送出。
3. **砍掉現有知識庫 SOP 裡「希望 AI 聰明判斷」的軟散文**
   在 AI/IC/WiFi 與曼報知識庫的自動化擷取管線中，只要牽涉到 URL 解析、檔案結構檢查、資料轉型，立刻拔除散文說明（例如：「請你仔細讀取並推斷作者後填入」），全數改用正規表示式（Regex）或明確的 Linter Python 工具做死，絕不給 AI 在這些基礎關卡留「44% 跳過步驟」的機會。

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

- [2026-08-03](daily/2026-08-03.md)
- [2026-07-30](daily/2026-07-30.md)
- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
