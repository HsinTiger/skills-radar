# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-08-05](daily/2026-08-05.md)

**今日一句話**：學界證實純自然語言形式的 Agent Skills 在執行時有高達 44% 的步驟跳過率與自作聰明的違規發揮，規格驗證絕對不能仰賴 Markdown 的文字指引，生態系正強力轉向「編譯為嚴格型別架構（Typed Harnesses）」與「基於 Git Worktree 的平行非同步架構」。

**短期建議（一週內）**

1. **立即實作 Pipeline 底層工具的「快速失敗 (Fail Fast)」機制**  
   針對今日抓取腳本引發 `[Errno 2]` 卻讓報告繼續前進的架構缺陷，應立刻在市場監控與知識庫的排程腳本最上層加上 dependency 嚴格檢查：
   ```bash
   command -v gh >/dev/null 2>&1 || { echo "CRITICAL: gh CLI missing in environment."; exit 1; }
   ```
   確保若底層相依損壞，系統立即發出告警並中斷管線，防範產生基於虛假或空數據的錯誤趨勢研判。
2. **針對 ccr / agy 主機執行空間的 Skills 進行「殭屍洗消」**  
   徹底清查自訂專案目錄與設定中的散裝 Markdown Skills。凡是沒有在 daily pipeline （如 Substack 或曼報整理）被每天直接命中的 skill 全部移除。越少不相關的 PROMPT 入口，你本地 Agent 執行關鍵任務時越不容易產生安全降級與胡亂發揮。

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

- [2026-08-05](daily/2026-08-05.md)
- [2026-08-04](daily/2026-08-04.md)
- [2026-08-03](daily/2026-08-03.md)
- [2026-07-30](daily/2026-07-30.md)
- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
