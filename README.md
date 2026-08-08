# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-08-08](daily/2026-08-08.md)

**今日一句話**：Claude Code 將預設開啟 Auto Mode（8/14 起），且支援跨 session 通訊，本機多 Agent 協作與全自動化基礎設施正在快速成形。

**短期建議（一週內）**

1. **檢視現有 CI/CD 與自動化 Pipeline 權限**：既然 Claude Code 即將預設開啟 Auto mode，請盤點本機或 pipeline 裡的自動化腳本，確保沒有把 `sudo` 權限、個人 SSH Private Key 或高權限 API Token 直接暴露在 Agent 可觸及的預設環境變數與目錄中。
2. **評估跨 Session 通訊的防火牆隔離**：將你目前的「市場監控」或「社群發文」pipeline 切分為兩個 Session。一個專門對外抓資料與解析（Read-only，高污染風險），一個專門負責寫入本地知識庫或發文（Write-only，無對外網路存取）。透過官方新支援的 cross-session messaging 傳遞純文字結構資料，阻斷 Injection 擴散。

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

- [2026-08-08](daily/2026-08-08.md)
- [2026-08-07](daily/2026-08-07.md)
- [2026-08-06](daily/2026-08-06.md)
- [2026-08-05](daily/2026-08-05.md)
- [2026-08-04](daily/2026-08-04.md)
- [2026-08-03](daily/2026-08-03.md)
- [2026-07-30](daily/2026-07-30.md)
- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
