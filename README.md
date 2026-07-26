# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-07-26](daily/2026-07-26.md)

**今日一句話**：Claude Code 官方發布 v2.1.219，預設模型正式升級為 1M Context 的 Opus 5，並引進 strictAllowlist 沙盒網路白名單防禦機制。

**短期建議（一週內）**

1. **啟用 Claude Code 嚴格網路白名單**：
   在 CLI 設定中加入 `sandbox.network.strictAllowlist`，僅允許 pipeline 必要的網域（如 Substack API、Cloudflare、指定數據源），全面阻擋非授權外連。
2. **檢視並吸收 Karpathy 防護規約**：
   不用直接安裝第三方 Skill，手動人肉審閱 `0xwilliamortiz/andrej-karpathy-skills` 中的 Markdown 內容，將其中防範「Agent 擅自重構運作中程式碼」的規則，抽離並寫入現有 pipeline 的 `.claude/rules` 或 agy 系統提示詞中。
   - **驗證步驟**：使用 `git clone` 下載至 `<appDataDir>/scratch/` 獨立目錄 ➔ 純文字人肉檢查是否有隱藏指令 ➔ 手動複製純規約內文。

## 生態指標

| repo | 目前 star | 自 2026-07-26 起變化 |
|---|---:|---:|
| anthropics/skills | 164,187 | +0 |
| anthropics/claude-plugins-official | 32,668 | +0 |
| anthropics/claude-code | 139,100 | -1 |
| ComposioHQ/awesome-claude-skills | 70,700 | +2 |
| travisvn/awesome-claude-skills | 14,317 | +1 |

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

- [2026-07-26](daily/2026-07-26.md)
