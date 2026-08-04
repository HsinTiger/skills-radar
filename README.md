# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-08-04](daily/2026-08-04.md)

**今日一句話**：純文字描述的 Agent Skills（Prose Skills）在實務執行上的高準確率是個幻想（論文證實僅 56% 遵循率），生態正急速往「編譯為型別限制的 Harness（Typed Harnesses）」與底層 Hook 監控的方向轉移。

**短期建議（一週內）**

1. **修復情報 Pipeline 系統環境報錯**：你的日常抓取報告今天全體回報 `[Errno 2] No such file or directory: 'gh'`。請立刻檢查排程（cron / launchd / subagent Sandbox）中的 `PATH` 變數，確保 `gh` 執行檔絕對路徑已載入，別讓 GitHub 變動監控因極致愚蠢的環境參數斷流。
2. **稽核 Claude Code / agy 權限設定**：參照 HN 「1/6 無效權限設定」情報，立即檢查你本機 CLI 與各種 automation pipeline 的 `.permissions` / ignore 設定檔。針對「唯讀、阻擋 Bash 外發連線、限制專案目錄」的規則，寫一個小模擬腳本用無害指令嘗試做破壞性嘗試，證明你的黑名單是物理有效，而不是心理防線。

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

- [2026-08-04](daily/2026-08-04.md)
- [2026-08-03](daily/2026-08-03.md)
- [2026-07-30](daily/2026-07-30.md)
- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
