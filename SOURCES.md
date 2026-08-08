# 來源清單與信任分級

## Tier 1 — 官方一手（當事實用）

| 來源 | 追蹤什麼 |
|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | 官方 Agent Skills 參考實作與規範。目前 17 個開源 skill。註冊為 marketplace：`/plugin marketplace add anthropics/skills` |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | Anthropic 維護的高品質 plugin 目錄，目前 39 個 |
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | Claude Code 本體：release、changelog、issue 風向 |
| [docs.claude.com](https://docs.claude.com) | Skills / plugin / API 官方文件 |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | MCP steering-group 維護的 reference servers；repo 自身明示非 production-ready |

⚠️ 即使是官方 repo 也有免責聲明：這些 skill **僅供示範與教學用途**，正式用途前需自行測試。

## Tier 2 — 安全研究（當警報用）

| 來源 | 說明 |
|---|---|
| [Snyk ToxicSkills 研究](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/) | 首份大規模 agent skill 生態安全稽核，3,984 個樣本 |
| arXiv（自動抓取） | agent skills security / prompt injection 相關新論文 |
| [Cloud Security Alliance](https://labs.cloudsecurityalliance.org/) | CI/CD 與 agent 供應鏈威脅研究 |

## Tier 3 — 社群訊號（**只當風向，不當品質背書**）

| 來源 | 說明 |
|---|---|
| [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | 最大社群精選清單 |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | Claude Code 取向清單 |
| Hacker News（自動抓取） | 討論熱度，看「大家開始在意什麼」 |
| GitHub 新建 skill repo（自動抓取） | 供給面訊號 |
| Agent-Reach／Headroom／Agentic Harness Engineering | reach、context 與 harness pattern 候選；只用 pinned source review，不直接安裝 |
| LangGraph／Langfuse／E2B／Composio | orchestration、observability、sandbox、integration pattern 候選；產品宣稱仍需獨立 canary |

被收錄進精選清單**不等於安全** —— Snyk 的研究正是在這類聚合站點上發現惡意樣本。

## ⛔ 高風險聚合站

`ClawHub`、`skills.sh` 這類開放投稿的 skill 市集是已知惡意樣本的主要分發管道
（2026-02 曾有 30+ 個惡意 skill 的協同散布行動，稽核當下仍有 8 個惡意 skill 在線）。
本 radar 會追蹤這類平台的**事件**，但不從中推薦任何 skill。

## 回答「GitHub 是唯一安全可靠的來源嗎？」

**不是，而且這個問題的前提就不對。**

GitHub 只是託管平台，不做內容審查。同一個 github.com 網域下同時存在 Anthropic 官方 repo
和一週齡帳號發布的惡意 skill —— 網域相同，可信度天差地別。

真正決定可信度的是三件事，與託管在哪裡無關：
1. **誰維護**（可究責的組織 / 具名維護者 / 匿名新帳號）
2. **你能不能讀懂它做了什麼**（skill 是純文字，這點比一般套件更可行 —— 也代表你沒有藉口不讀）
3. **它要求什麼權限**（碰不碰金鑰、config、外部網路）

順帶一提：`github.com/SKILLS` 是 GitHub 官方的**教學課程**組織（教人怎麼用 GitHub），
跟 Agent Skills 完全無關，別找錯地方。
