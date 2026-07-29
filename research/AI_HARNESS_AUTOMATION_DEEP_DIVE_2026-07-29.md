# AI Application／Agent Harness／Automation Deep Dive — 2026-07-29

> `NX_CONTEXT=SNAPSHOT_ONLY`。本文只使用公開來源與 pinned source review；沒有安裝或執行任何第三方 skill、framework、MCP server，也沒有讀取 cookie、登入 session、私人貼文或公司資料。

## Executive view

明確趨勢不是「代理可以再多爬幾個網站」，而是模型與單點工具快速商品化後，工程價值正上移到 **governed agent harness**：資訊入口、脈絡壓縮、持久狀態、工具路由、評測觀測、隔離執行與證據契約開始成為同一個控制平面。

這也指出一條比通用 prompt engineering 更適合 owner 的潛力賽道：**Evidence-Governed Domain Agent Harness**。聚焦高風險工程與 ASIC automation，把設計意圖、驗證意圖、確定性執行包、真實工具證據與 owner approval 串成可恢復、可稽核的鏈。公開專案提供 pattern；真實 EDA 正確性仍只能由核准環境的 VCS、Verdi、synthesis、formal／LEC 等工具證據提升。

## 為什麼 Agent-Reach 有趣，但不該整包採用

Agent-Reach 的核心不是爬蟲，而是 capability registry。每個平台有 ordered backends，`doctor` 回報 active backend、錯誤與修復路徑；單一 channel 失敗不拖垮整體。其 contract tests 也驗證 backend 排序、channel 狀態與 credential-backed doctor 不自動建立或刷新憑證。這些都是好的 harness pattern。

但 repo 同時明示 Twitter、Reddit、Facebook、Instagram 與小紅書需要 cookie 或既有瀏覽器 session，並警告 script/API 可能導致封號。Cookie 等同帳號完整登入權，且上游 CLI、MCP server、瀏覽器會話與平台規則形成很大的供應鏈、隱私及 ToS 表面。

結論是 `B / WATCH`：

- 採用：capability registry、health probe、ordered fallback、credential scrubbing、safe/dry-run 思路。
- 僅限：公開 Web、RSS、GitHub、YouTube 等合法公開入口。
- 排除：私人貼文、自動登入、cookie 匯入、讀取瀏覽器 session、反反爬、CAPTCHA、住宅代理或規避平台限制。

## 八個候選的 portfolio 判讀

| 角色 | 候選 | 判讀 | 對 domain harness 的價值 | 主要風險 |
|---|---|---|---|---|
| Reach routing | Agent-Reach | B / WATCH | capability probe、fallback、doctor | cookie、封號、ToS、upstream supply chain |
| Context | Headroom | B / WATCH | reversible compression、cache stability、metrics | benchmark 未重現、proxy 改寫與 constraint loss |
| Governance | Agentic Harness Engineering | A / PILOT | failure trace、change manifest、rollback | 固定 topology 與分數可能造成假精確 |
| Orchestration | LangGraph | A / PILOT | checkpoint、interrupt/resume、conformance | framework 反客為主、side-effect idempotence |
| Observability | Langfuse | B / WATCH | trace、dataset、eval linkage、self-host | prompt/trace 機密、telemetry、mixed license |
| Sandbox | E2B | B / WATCH | execution lifecycle、artifact contract | 外部 cloud realm、API key、network egress |
| Tool protocol | MCP reference servers | A / PILOT | typed discovery、scope、reference tests | 官方明示非 production-ready、server quality 不一 |
| Integration | Composio | C / WATCH | runtime discovery、scoped session | pre-auth actions、hosted session 與 credential blast radius |

評級只代表「能否進入公開資料 canary」，不是已安裝、已採用或已上線。所有 stars、token savings、平台覆蓋與 benchmark 都是待重現的來源宣稱。

## 專業情報 thesis

### 核心主張

代理生態正由「模型加一堆 tools」轉向「有 policy 的 execution substrate」。這個 substrate 需要知道工具現在能不能用、誰可用、能讀寫什麼、失敗後從哪裡恢復、輸出如何連回 oracle，以及哪一步必須由 owner 批准。

### 反方觀點

原生模型平台可能快速吸收 compaction、tool discovery、trace 與 sandbox，讓今日框架被壓成薄薄的一層。熱門 repo 的成長也可能只是行銷與 GitHub 注意力，而不是 enterprise demand。真正能留下來的不是 framework 名稱，而是 domain-specific evidence contract 與可攜 state schema。

### 催化劑

- tool 數量增加，runtime discovery 與最小權限比把所有 schema 塞進 context 更重要；
- 長任務需要 conversation 外的 checkpoint、retry、cancel 與 readback；
- 企業要求 evaluation、sandbox、資料邊界與 human approval 同時成立；
- 模型能力與價格收斂，使可靠執行與 domain proof 成為更持久的差異化。

### 領先指標

- 專案是否從 agent demo 轉向 `doctor`、conformance、checkpoint、rollback 與 negative tests；
- auth 是否由長效共享 credential 轉向 scoped、revocable session；
- trace 是否能連回確切 input version、tool call、artifact、oracle 與 failure class；
- sandbox 是否能讀回 network、filesystem、process、credential 與 artifact policy；
- 同一 contract 是否能跨至少三個 domain tasks 重現，而不是只在單一 demo 成功。

## 個人化搭建方向：先 evidence kernel，再 agent autonomy

建議控制平面依序形成：

1. **Evidence kernel**：task ID、design/verification intent、assumption、owner disposition、input hash、tool version、artifact manifest、claim boundary。
2. **Typed tool registry**：capability、scope、preflight、negative authorization、active backend 與 failure reason。
3. **Durable run governor**：checkpoint、idempotence key、retry budget、cancel、resume 與 manual recovery。
4. **Context layer**：先做可逆壓縮；任何 constraint、failure、owner decision 或 tool evidence 不得靜默刪除。
5. **Evaluation rail**：trace 連回 oracle、assertion、coverage denominator、LEC point count 與 exact report readback。
6. **Sandbox policy**：公開 fixture 可用通用 sandbox；內部 RTL、EDA license 與機密 log 留在核准環境。
7. **ASIC domain adapter**：OA 只產 owner-approved deterministic bundle；NX 跑真工具並回傳獲准證據，敘事不能代替 run evidence。

## 九十天路線

### 前一個月：控制面骨架

用公開 fixture 完成 evidence schema、change manifest、tool registry、checkpoint 與 negative authorization tests。先量測失敗能否被重現，不追求大量 agent features。

### 第二個月：公開 toy RTL canary

把 intent、candidate RTL／SVA／test、simulation artifact 與 claim audit 串成可恢復流程。context compression 必須有 uncompressed holdout；observability 只收去識別化 trace。

### 第三個月：核准環境的 deterministic bridge

以一個明確小任務建立 portable bundle、preflight、one-entry command、expected outputs、fail conditions 與 evidence manifest。只有真實工具 readback 能提升對應 claim；agent report 只負責整理而不擁有真相。

## 分析面板計畫：不同周期回答不同決策

| 周期 | 必答問題 | 主要方法 | 對 WiFi ASIC 前端的輸出 |
|---|---|---|---|
| 日 | source、license、credential 或安全邊界今天有沒有漂移？ | pinned diff、doctor/readback、只記新事實與反證 | 阻止漂移或登入型 adapter 混進 automation |
| 週 | 哪一個 harness 角色缺口值得一條端到端 canary？ | 公開 fixture 的 before/after trace、checkpoint、rollback 與 negative test | spec→intent→RTL/SVA→sim evidence 的可恢復交接 |
| 月 | 哪些工具正在收斂成控制平面，哪裡是高痛但稀缺的空白？ | thesis／anti-thesis、portfolio cut、跨 repo interface 與 failure replay | intent、tool evidence、debug handoff、前端 ECO audit 元件 |
| 季 | 同一 evidence contract 能否跨三種高風險任務重現？ | reproducibility、owner interruption、recovery effort、外部需求訊號 | Evidence-Governed Domain Agent Harness 的 build/buy/learn 押注 |

利基判斷不以 stars 排名。優先尋找「工程失敗代價高、公開供給稀疏、模型能力提升後仍離不開 domain oracle／evidence／approval」的交集。目前三個優先假設是 RTL／DV Evidence Kernel、EDA Tool Capability Registry 與 Frontend ECO Failure Replay。Jupyter notebook 可作 cohort、trend 與利基地圖的探索工作台，但任何正式結論都必須回寫 versioned JSON、deterministic builder 與測試；notebook 本身不是 production truth。

## 歷史資料契約

第三專區從 `2026-07-29` 開始保存每日 observation tape。今日以前的 GitHub `repo_created`、`first_seen` 與舊 corpus 只能作史料，不能偽造成每日監控記錄。日尺度看 source drift 與風險；週尺度看一條 canary；月尺度看 portfolio 斷點；季尺度才判斷跨任務重用與產品化可能。

## Pinned evidence

- Agent-Reach：`b4d52c46c9113cb0f653d6df4cf71ebadf4930ac`
- Headroom：`1588f5e04144af5de8398810ea3893c6e623309c`
- Agentic Harness Engineering：`faf44bc4aea57413c520bc5711c6ebf628e0da1e`
- LangGraph：`41341457342327166d72fc11952ab28fb61ec0bf`
- Langfuse：`90b98d009a6d4c4ce46a5a6dc5187b661bfdd804`
- E2B：`cf8296cf8997f98aefd6e8236d4d235f5ab1ddad`（unsigned）
- MCP reference servers：`d31124c982401739917fd817c2a59db344529c16`
- Composio：`3335bb30134f97b5e12a1c54d6daa821e0d8106e`

完整逐項 evidence、dependency、risk 與 source URL 位於 `corpus/ai_automation_skill_reviews.json`。
