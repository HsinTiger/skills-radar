# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

## 最新一期：[2026-07-26](daily/2026-07-26.md)

**今日一句話**：Claude Code 釋出 v2.1.219/220 支援 Opus 5 1M 長上下文與沙盒嚴格網路白名單；同時學界與社群全面轉向防範「長上下文下的 Skill 規範衰退」與「多 Agent 間的 Channel Injection 防禦」。

**短期建議（一週內）**

1. **啟用 `sandbox.network.strictAllowlist` 防禦 CLI 自動化外連風險**
   - **具體動作**：更新 Claude Code 至 `v2.1.219+`，在本地全域設定檔啟用 `strictAllowlist`，僅放行 Substack API、BTC 數據源、GitHub 等必要 Domain。阻斷所有未授權的背景外連。
2. **抽取防護型規則至自建全域 System Rules (如 `agy` / `ccr` / `Claude Code`)**
   - **驗證步驟**：
     1. 下載 `0xwilliamortiz/andrej-karpathy-skills` (T3) 原始檔。
     2. 檢查其 `.md` 內容，確認無惡意 Prompt 或外聯網址。
     3. 僅複製其「反模式負面條款」（如禁止動非相關檔案、禁止偽造 API 回應），貼入本地控制層 Prompt，強化 CLI 稽核能力。

## 生態指標（首次快照）

| repo | star |
|---|---:|
| anthropics/skills | 164,187 |
| anthropics/claude-plugins-official | 32,668 |
| anthropics/claude-code | 139,101 |
| ComposioHQ/awesome-claude-skills | 70,698 |
| travisvn/awesome-claude-skills | 14,316 |

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
