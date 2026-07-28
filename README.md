# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-07-28](daily/2026-07-28.md)

**今日一句話**：生態快速轉向「特權隔離（Privilege Separation）」與「Harness 工程治理」，今日官方 GitHub 資料因擷取工具異常無事實更新。

**短期建議（一週內）**

1. **建立 Substack / 市場監控 Pipeline 的「讀寫特權分離」**：將網路爬蟲與外部資料抓取模組限縮在無本機檔案寫入與 Shell 執行權限的純解析環境，嚴禁將未過濾的網頁原文直接丟給帶有高執行權限的本機 CLI（Claude Code / agy）。
2. **導入 Token 佔用率診斷（Context Profiling）工具驗證**：針對既有 IC 知識庫 pipeline，檢查是否有重複載入厚重 prompt 的情況，清理不必要的 context 消耗。

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

- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
