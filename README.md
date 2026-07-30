# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-07-30](daily/2026-07-30.md)

**今日一句話**：Agent 授權邊界與工作流的安全隔離成為學界與社群焦點，從「能做什麼」轉向「如何防止被濫用」。

**短期建議（一週內）**

- **盤點本機 Pipeline 的 Context 共享機制**：檢視你現有的 AI/IC/WiFi 知識庫與曼報抓取 pipeline。如果負責爬蟲的 Agent 與負責總結/發文的 Agent 共享同一個 context 或是系統讀寫權限，必須立刻切分。將外部抓取的資料視為「受污染 (Tainted)」，僅允許沙盒內的唯讀 Agent 處理，再將淨化後的結構化 JSON 交給下游 Agent。
- **建立 Token 與執行時間的稽核卡點**：鑒於社群對 API 延遲與成本的反應，如果你的 pipeline 大量依賴 agy / ccr 處理厚重任務，建議寫一支輕量的 bash script 去 parse 執行 log，撈出耗時最長、Token 用量最大的環節，決定哪些步驟該改用輕量模型或純 Python script 取代。

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

- [2026-07-30](daily/2026-07-30.md)
- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
