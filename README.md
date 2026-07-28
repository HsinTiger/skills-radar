# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-07-27](daily/2026-07-27.md)

**今日一句話**：長 Context 導致 Skill 指令衰退與多 Agent 跨通道攻擊（Channel Attack）研究同步爆發：你的自動化 Pipeline 當前最大的出局風險不在模型智商，而在「未隔離的 Agent 中繼通道」與「一次性載入巨型 Skill 的指令失效」。

**短期建議（一週內）**

1. **防禦檔案遺失與歷史清理**：檢查本機 `claude-code` 與 `agy` 執行的工作目錄。為所有自動化 Pipeline（Substack 發文、知識庫更新）建立獨立 git 工作區，並在 Cronjob 中加入「執行完畢自動 git status 比對與自動 Push」機制，防止 30 天本機 Context 遭刪除或檔名誤刪造成不可逆損失。
2. **精簡巨型 Skill 檔**：盤點目前使用的自訂 Skill，若有單一檔案超過 300 行的「大百科型 Skill」，立即拆解。改為僅保留摘要導引，詳細規格改由 Agent 根據子任務動態讀取，以解決長 Context 下的指令衰退問題。

## 專題研究

- [每日 EDA_IC／財經投資研究 Skill 建議](research/recommendations/2026-07-27.md)：
  每日 08:30 以 deterministic gate 更新；`pilot` 只代表可進入隔離評估，不代表已安裝、已上線或通過正確性驗證。
- 日／週／月／季 AI Summary：單一 08:30 dispatcher 只分析上一個完整期，依 `period_id` 補跑漏期；
  AI narrative 與 deterministic evidence cards 分離，沒有 fresh canonical corpus 就不產生摘要。
- [WiFi ASIC RTL / EDA Skill 適用性研究（2026-07-27）](research/ASIC_WIFI_SKILL_FIT_2026-07-27.md)：
  排除 FPGA、embedded、board/PCB、analog/RF，逐項審查可改編的 RTL/EDA procedure；
  current catalog 因 canonical corpus 與 golden labels 尚未完成而明確標為 `BLOCKED`。

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
bin/wiki_ingest.py 累積各領域 evidence snapshot，產生 research/wiki 與 docs/wiki 實體頁面
bin/wiki_query.py  查詢最新 Wiki snapshot（不讀第三方原文）
bin/build_daily_recommendations.py  產生 EDA_IC／財經投資研究的每日採用候選、摘要與風險 gate
bin/timescale_summaries.py  日／週／月／季 evidence、AI summary、完整期與 catch-up dispatcher
bin/write_pipeline_health.py  公開最後一次本機 gate 狀態；remote/Pages 仍須另做 readback
bin/check_published_freshness.py  GitHub Actions 每日 09:30 watchdog，讓漏跑／stale 狀態明確失敗
data/snapshot.json  上次狀態（用於 diff 出「今天有什麼變了」）
data/wiki_history.json Wiki 的 append-only evidence history（同日修正需 revision note）
data/history.jsonl  指標時序
daily/YYYY-MM-DD.md 每日簡報
```

排程：launchd `com.hsin.skills-radar` 每日 08:30 執行 dispatcher；日摘要每天、週摘要每週一、
月摘要每月一日、季摘要每季首月一日更新上一完整期。離線後補跑缺少的 `period_id`。
手動跑一次：`~/skills-radar/bin/run_daily.sh`

## 歷史簡報

- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
