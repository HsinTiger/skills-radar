# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-08-07](daily/2026-08-07.md)

**今日一句話**：業界正試圖統一 AI Agent 的 Skill 與 Plugin 標準，同時學術界針對 Agent 系統的間接提示詞注入（IPI）與技能安全風險爆發大量研究。

**短期建議（一週內）**

1. **盤點認證邊界**：檢視你現有 pipeline 中 agy 或 ccr 是否擁有自動存取密碼管理員或執行敏感登入的權限。若有，立即加入 Human-in-the-loop 阻斷點，避免遭到網頁內容的 IPI 攻擊（參考 LoginTrap 研究）。
2. **評估 Uber ADR 監控機制**：前往 `uber/ADR` repo 檢閱其開源架構。**不要直接安裝**，先閱讀程式碼了解大廠如何攔截與稽核 Agent 的底層系統呼叫，評估是否能整合進你本機的 CLI 流程中作為第二道防線。

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
