# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-08-06](daily/2026-08-06.md)

**今日一句話**：自動化情報爬蟲因缺少 `gh` 指令全線崩潰；學術界與社群同步證實「靜態審查無法防範 Skill 動態攻擊」與「自主管線極易產生偽造成功的靜默失效」，未靠物理隔離與唯讀限制的委外 CLI 是當前最大的系統性出局風險。

**短期建議（一週內）**

1. **立刻修復本機 Crawler Pipeline 的 `gh` 依賴缺失**
   - 你的抓取系統報錯 `No such file or directory: 'gh'`。檢查此份自動化情報產線的 cron job / Python harness 執行環境，確實安裝 GitHub CLI 或將 `/opt/homebrew/bin` 等二進位目錄宣告至執行腳本的 `PATH`。
2. **為 Substack / 曼報 / 市場監控管線建立「去 AI 化」的終極成果稽核**
   - 應對 LLM 偽造成功（Faking success）的共識盲區：檢查管線的驗收步驟，**全面拔除「問 LLM 檔案作得對不對」這類偽稽核**。直接在你的 Bash/Python 架構中用 `test -s [file]`（驗證位元組 > 0）、結構 JSON Schema Validation 或 SHA256 比對來充當過關條件，出錯直接中止發布並送 Alert，防止瑕疵品上路破壞個人商業信用。
3. **對現有知識庫檢索實施欄位分離（Field-Aware Retrieval）準備**
   - arXiv 最新研究 (2608.02880) 證明，將 Skill/文件名稱、描述和本文合爲一段（Flat text）塞給 Agent 做向量檢索，將成為精度樽頸。若你的 AI/IC/WiFi 知識庫或 Local Skills Bank 有破百規模，應在資料庫與 Prompt 設定上強制維持欄位隔離，只用 Description+Name 尋找候選，而非全文暴力比對。

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

- [2026-08-06](daily/2026-08-06.md)
- [2026-08-05](daily/2026-08-05.md)
- [2026-08-04](daily/2026-08-04.md)
- [2026-08-03](daily/2026-08-03.md)
- [2026-07-30](daily/2026-07-30.md)
- [2026-07-29](daily/2026-07-29.md)
- [2026-07-28](daily/2026-07-28.md)
- [2026-07-27](daily/2026-07-27.md)
- [2026-07-26](daily/2026-07-26.md)
