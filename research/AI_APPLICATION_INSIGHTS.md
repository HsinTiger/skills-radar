# AI 應用行為研究 — 從 5397 個公開 Agent Skill 看見的事

## 研究摘要

1. **開源 Agent 生態本質上是「工程師寫給工程師用的腳本庫」**：`software-dev`（33.5%）、`ai-agent-tooling`（15.6%）、`devops-infra`（6.2%）與 `security`（4.9%）四大開發領域合占整體樣本的 60.2%。推論：AI 應用的開源生態極度偏重技術從業者，非技術人員的自動化浪潮在公開 GitHub 上尚未真正爆發。
2. **AI 被當作「寫程式與系統配置」的產出器，但「斷言與檢查」的機制嚴重脫節**：整體任務以 `generate`（21.9%）、`configure`（17.1%）與 `orchestrate`（15.6%）為主力，`verify` 僅占 15.0%。更殘酷的是在 `ai-agent-tooling` 領域中，`orchestrate`（261 件）與 `configure`（250 件）占據 60.5%，`verify` 卻只有 67 件（7.9%）。推論：大家正熱衷於搭建越來越複雜的 Agent 堆疊與調度鏈，卻極度缺乏自動化稽核關卡，導致 Agent 系統極易崩潰於邊界條件。
3. **剛性合規與高風險領域的「生產成熟度」遠高於一般輔助領域**：`security`（production 64.9%）、`legal-compliance`（production 63.6%）、`devops-infra`（production 62.6%）與 `healthcare-bio`（production 53.4%）的正式上線比例遠高於總體平均（42.3%）。推論：越是容錯率低、責任嚴重的領域，使用者越不敢寫概念性玩具（`security` 的 `toy` 僅 4 件），只要出手的 Skill 都是為了打通真實的生產合規管線。
4. **個人生產力與行銷領域仍停留在「工作流草稿」階段**：`personal-productivity`（workflow 69.3%、production 21.5%）與 `marketing-growth`（workflow 62.9%、production 35.6%）絕大多數停留在工作流嘗試。推論：這類非結構化任務缺乏硬性 API 邊界與確定性斷言，導致大量 Skill 只能當作臨時 Prompt 範本，無法升級為穩定的自動化模組。
5. **「Agent 給 Agent 用」的介面已占據 16.9% 的市場**：在 `target` 欄位中，`agent`（16.9%）已成為僅次於 `team`（36.1%）與 `self`（35.2%）的第三大受眾。推論：Skill 已不再只是人機互動的指令指南，而是逐漸演變為多 Agent 協同（Agent-to-Agent）的模組化程式介面。
6. **開源生態中隱藏 87 筆（1.61%）潛在 Prompt Injection 風險**：`injection_suspect` 統計達 87 筆。推論：使用者在直接引入 GitHub 第三方 Skill 時，正面臨供應鏈安全威脅，未經稽核的 Skill 可能越權執行未授權的本機指令。
7. **硬體 IC/EDA 領域極度稀缺（僅 36 件，0.7%）**：`hardware-eda` 樣本數僅 36 件。推論：晶片設計並非不需要 AI，而是因為高昂的保密協定（NDA）、閉源 EDA 工具鏈以及零容錯的 Tape-out 門檻，使該領域的自動化成果全部閉鎖於企業防火牆之內。

---

## 一、AI 到底被誰在用

統計顯示，領域分佈前三名分別為 `software-dev`（1809 件，33.5%）、`ai-agent-tooling`（844 件，15.6%）與 `devops-infra`（337 件，6.2%）。若觀察前 30 大職業，`軟體工程師`（638 人）、`前端工程師`（356 人）、`AI工程師`（245 人）、`後端工程師`（215 人）與 `DevOps工程師`（150 人）佔據絕對主導地位。

### 意外出現的領域
- **資安與法務的公開參與度高於預期**：`security` 達 265 件（4.9%），`legal-compliance` 達 88 件（1.6%）。儘管法務與資安受高監管限制，但在開源社群中，紅藍隊演練與合規檢查腳本的的需求十分剛性（如 `mukul975/Anthropic-Cybersecurity-Skills` 擁有 26,583 stars）。
- **小眾專業領域的具體痛點落地**：資料中出現了 `逆向物流經理`（退貨欺詐檢驗，233,406 stars）、`教會法律師`（天主教法典條文檢索，1,381 stars）、`命理師`（八字排盤與命理計算，2,289 stars）與 `辯論選手`（論點構建，1,184 stars）等跨界角色。推論：當領域專家具備基本 Prompt 與腳本編寫能力時，Agent Skill 能迅速填補極度垂直、大廠商不屑做的小眾需求。

### 意外缺席的地方
- **`sales-crm` 僅占 50 件（0.9%）**：業務與 CRM 本應是企業變現的核心，但 Skill 數量極少。推論：B2B 業務人員普遍缺乏將工作流打包為 GitHub Markdown/JSON 技能檔的工程能力，且 CRM 工具（如 Salesforce、HubSpot）多被封閉的 SaaS UI 綁定。
- **`hardware-eda` 僅占 36 件（0.7%）**：在 5,397 件樣本中幾乎邊緣化。缺席的原因在於晶片設計產業嚴苛的智慧財產權（IP）與 NDA 限制，以及 Cadence/Synopsys 等 EDA 工具鏈昂貴且封閉的特性，工程師無法將產線上的 RTL 或 UVM 技能公開上傳。

---

## 二、大家讓 AI 做哪一層的工作

從整體 task 分佈來看，任務呈現以下層級：
- `generate`：1,184 件（21.9%）
- `configure`：921 件（17.1%）
- `orchestrate`：840 件（15.6%）
- `verify`：811 件（15.0%）
- `analyze`：674 件（12.5%）
- `retrieve`：536 件（9.9%）
- `transform`：431 件（8.0%）

`target` 受眾分佈則顯示：`team`（1,948 件，36.1%）與 `self`（1,899 件，35.2%）平分秋色，而專門設計給 `agent` 呼叫的介面達 912 件（16.9%）。

```
[各領域核心 Task 分佈差異]
- 創意/寫作類 (design-creative, writing-content)  ---> 絕對集中於 generate
- 決策/生醫類 (finance-investing, healthcare-bio)   ---> 絕對集中於 analyze
- 基礎架構類 (devops-infra, ai-agent-tooling)     ---> 集中於 configure & orchestrate
- 資安/法務類 (security, legal-compliance)         ---> 絕對集中於 verify
```

### 交叉分析 `domain × task`
不同的行業在使用 AI 時，定位截然不同：

1. **作為「生成產出工具」**：
   - `design-creative`：`generate` 占 211 件（共 324 件，65.1%）。
   - `writing-content`：`generate` 占 70 件、`transform` 占 59 件（共 166 件，77.7%）。
   - 這類領域將 AI 純粹視為草稿生成器或格式轉換器。
2. **作為「品質與合規把關者（Verify）」**：
   - `security`：`verify` 達 152 件（共 265 件，57.4%），其餘 `analyze` 43 件。
   - `legal-compliance`：`verify` 達 29 件（共 88 件，33.0%）。
   - 資安與法務不相信 AI 的自主生成，只把 AI 當成檢查漏洞（如 BOLA/IDOR 測試）與合規審查的斷言工具。
3. **作為「資料分析與決策大腦（Analyze）」**：
   - `finance-investing`：`analyze` 達 81 件（共 182 件，44.5%）。
   - `healthcare-bio`：`analyze` 達 58 件（共 116 件，50.0%）。
   - 金融與生醫領域中，`generate` 比例極低（生醫僅 1 件），AI 的核心價值在於結構化數據解析與變異預測。
4. **作為「系統調度與環境配置中樞（Orchestrate & Configure）」**：
   - `ai-agent-tooling`：`orchestrate`（261）與 `configure`（250）合計占 60.5%。
   - `devops-infra`：`configure`（142）與 `orchestrate`（71）合計占 63.2%。
   - 開發與維運工具鏈中，AI 被用來拉通 CLI 命令、編排 CI/CD 與調度背景任務。

---

## 三、玩具還是生產線

整體成熟度 `maturity` 分佈為：
- `workflow`（工作流/半成品）：2,855 件（52.9%）
- `production`（正式上線/高可靠）：2,283 件（42.3%）
- `toy`（概念驗證/玩具）：259 件（4.8%）

### 領域成熟度對比（`domain × maturity`）

| 領域 | Production 數量 (比例) | Workflow 數量 | Toy 數量 (比例) | 狀態評估 |
| :--- | :--- | :--- | :--- | :--- |
| **security** | **172 (64.9%)** | 89 | 4 (1.5%) | 硬核生產線 |
| **legal-compliance** | **56 (63.6%)** | 31 | 1 (1.1%) | 硬核生產線 |
| **devops-infra** | **211 (62.6%)** | 116 | 10 (3.0%) | 硬核生產線 |
| **healthcare-bio** | **62 (53.4%)** | 52 | 2 (1.7%) | 硬核生產線 |
| **data-analytics** | **68 (52.7%)** | 59 | 2 (1.6%) | 硬核生產線 |
| **ai-agent-tooling** | 382 (45.3%) | 361 | **101 (12.0%)** | 兩極化嚴重 |
| **software-dev** | 750 (41.5%) | 1015 | 44 (2.4%) | 主力工作流 |
| **personal-productivity** | 65 (21.5%) | **210 (69.3%)** | 28 (9.2%) | 試驗玩具區 |
| **education-training** | 13 (16.7%) | 54 | **11 (14.1%)** | 試驗玩具區 |

推論：指標直接揭露了領域特性——**凡是允許人工事後修正的領域（個人生產力、教育、行銷），Skill 大多停留在概念或半成品；凡是錯誤代價極高、必須一次做對的領域（DevOps、資安、法務、生醫），Skill 的 Production 比例直接衝破 50%~65%**。

`ai-agent-tooling` 的 `toy` 比例高達 12.0%（101 件），反映出社群大量在做 Agent 框架的實驗性輪子，但缺乏落地場景。

---

## 四、真正的痛點長什麼樣

從 `pain_samples` 跨領域歸納，使用者寫下 Skill 的痛點存在四大共通模式：

### 模式一：跨工具鏈與 CLI 命令分散、憑證管理混亂（Context-Switching & Toolchain Friction）
工程師最痛的不是不會寫程式，而是切換工具、記憶 CLI 參數與處理 API 憑證授權。
- **DevOps**：`twentyhq/twenty` (53,654 stars) — 「Twenty 應用程式營運與部署命令分散繁瑣」。
- **Ops-Admin**：`Hmbown/CodeWhale` (40,116 stars) — 「飛書與 Lark API 整合時憑證管理混亂」。
- **Design**：`krillinai/KrillinAI` (10,550 stars) — 「影片字幕、配音與跨平台渲染 CLI 操作複雜」。

### 模式二：高重複性數據拉皮、格式轉換與對帳耗時（Data Scraping & Formatting Fatigue）
非結構化資料轉為結構化報告時，人工手動對帳與格式調整極易出錯且效率低下。
- **Finance**：`anthropics/knowledge-work-plugins` (23,042 stars) — 「總帳與子帳或銀行對帳單人工核對繁瑣易錯」。
- **Research**：`opensquilla/opensquilla` (6,341 stars) — 「論文草稿撰寫前引用文獻與 BibTeX 對應混亂」。
- **Ops-Admin**：`Intelligent-Internet/ii-agent` (3,368 stars) — 「手動處理與填寫批量 PDF 文件效率低下」。

### 運動三：人工審查與邊界條件遺漏導致的安全/合規漏洞（Compliance & Audit Bottlenecks）
靠人類肉眼去對齊複雜規範（如資安漏洞、合規條款、無障礙規範）幾乎必然遺漏。
- **Security**：`mukul975/Anthropic-Cybersecurity-Skills` (26,583 stars) — 「手動測試 API BOLA/IDOR 越權漏洞繁瑣耗時」。
- **Legal**：`AgentEra/Agently` (1,632 stars) — 「人工審閱廠商合約容易遺漏關鍵條款」。
- **Software-Dev**：`thedaviddias/Front-End-Checklist` (73,320 stars) — 「行內 JS 導致 CSP 違規與快取維護困難」。

### 模式四：Agent 背景執行失控、進度不可追蹤與消極放棄（Agent Execution Drift）
當工作外包給 Agent 後，使用者面臨的是 Agent 狀態不可見或中途停滯。
- **AI-Agent-Tooling**：`sickn33/agentic-awesome-skills` (43,916 stars) — 「難以同時調度與監控多個背景運行的 Agent」。
- **AI-Agent-Tooling**：`sickn33/agentic-awesome-skills` (43,916 stars) — 「追蹤與核對 Agent 承諾事項之執行結果費時」。
- **Personal Productivity**：`wuji-labs/nopua` (1,367 stars) — 「AI 在任務失敗後容易消極放棄或回覆推託」。

---

## 五、時間軸告訴我們什麼

從 `timeline_by_month`（2025-05 至 2026-07）的動態演進可以看出生態的擴散軌跡：

```
2025-05 ~ 2025-09 (醞釀期)  : 月均約 15~35 件，完全由 software-dev 與 ai-agent-tooling 包辦。
2025-10 ~ 2025-12 (起飛期)  : software-dev 從 34 件增至 79 件，devops、design、ops 開始穩定出現。
2026-01 ~ 2026-04 (爆發期)  : 2026-03 達到頂峰（software-dev 274 件, ai-agent-tooling 174 件, 
                              design 56 件, devops 56 件, personal 55 件, security 54 件）。
2026-05 ~ 2026-07 (收尾期)  : 總量下降（2026-07 為 73 件）。
                              誠實說明：2026-07 數字銳減主要是因為資料採集截止日影響，非實際衰退。
```

推論：**Agent Skill 生態在 2025 年第四季完成技術封閉圈（Dev）的驗證後，於 2026 年第一季迅速向資安、行銷、個人生產力等非核心開發領域擴散。** `legal-compliance` 在 2026-05 突然激增至 31 件，顯示專業法律領域對 CLI/MCP 技能的導入存在約 3-6 個月的時間滯後。

---

## 六、對讀者的意涵

### 你的自動化體系該補哪一塊

讀者現有的本機自動化體系（電子報發文、知識庫、市場監控、社群發文）已涵蓋基礎流轉，但基於資料顯示的空白，建議補強以下兩塊：

1. **補上「Verify 規格與斷言自動化門禁層」**：
   - 資料顯示，`ruvnet/ruflo`（66,003 stars）等頂級 Skill 的核心都在做發布前的自動格式與規則校正。
   - 讀者的 Substack 與社群發文流水線目前較偏重生成與調度。推論：應在發文腳本前置加入獨立的 `Verify` 門禁（如台灣用語與排版規範檢查、連結有效性比對），防止 LLM 幻覺內容直接過版。
2. **建置「背景多 Agent 執行狀態監控與反消極 Guardrail」**：
   - 重度使用 CLI（Claude Code / agy / ccr）外包任務時，資料中最顯著的痛點是「背景 Agent 難以監控」與「失敗後消極放棄」（`wuji-labs/nopua`）。
   - 建議在 CLI 外包架構上堆疊一層輕量監控腳本，當背景 Agent 停滯或報錯時自動重試或發送 Telegram 通知，而非等手動稽核時才發現 Agent 卡死。

### 可以寫成內容的非共識觀點

1. **《別再蓋 Agent，你缺的是斷言稽核》**
   - **非共識說明**：當全網都在熱衷談論如何用 AI 生成內容與編排流程時，資料顯示 `ai-agent-tooling` 的 Verify 比例只有 7.9%；真正決定 Agent 能否進入 Production 的關鍵，不是讓它寫更多 code，而是寫死 Rule-based 的驗證斷言。
   - **HOOK**：蓋了 10 個 Agent，不如寫一條硬 Check。
2. **《為何最懂 AI 的人，反而很少公開用它？》**
   - **非共識說明**：媒體宣傳 AI 正在顛覆實體產業，但 GitHub 揭露性偏好顯示硬體 IC/EDA 領域僅占 0.7%；最硬核的工程領域不是不採用 AI，而是因為高價值 Know-how 與 NDA 圍牆，開源生態根本看不到真實的AI戰場。
   - **HOOK**：0.7% 的聲量，藏著晶片業最深的壁壘。
3. **《個人生產力 Skill，九成都是無法上線的玩具》**
   - **非共識說明**：大眾以為用 AI 整理筆記與代辦事項是剛需，但數據顯示個人生產力領域的 Production 比例低至 21.5%（workflow 占 69.3%）；缺乏邊界與硬 API 約束的個人 Skill，最終都只是一時新鮮的 Prompt 玩具。
   - **HOOK**：你的 PKM 技能，只是一堆帶不走的提示詞草稿。

### 你所在的 IC/EDA 領域，資料說了什麼

`hardware-eda` 在 5,397 件總樣本中僅占 **36 件（0.7%）**。其成熟度為：`workflow` 22 件（61.1%）、`production` 13 件（36.1%）、`toy` 1 件（2.8%）。

痛點集中在：
- 手動調整晶片架構參數尋求最佳化耗時 (3,081 stars)
- 手動撰寫 UVM 測試平台與覆蓋率驗證耗時 (1,586 stars)
- 嵌入式開發工具鏈複雜且指令模糊難判斷 (757 stars)
- 從布爾邏輯規格手動推導與轉換閘級電路繁瑣 (26 stars)

**解讀與研判**：
36 件這數字極小，但這絕非代表 IC 設計不需要 AI。推論：
1. **極高保密壁壘（IP/NDA）**：IC 設計廠的 RTL 代碼、Testbench 與 EDA 腳本屬於核心商業機密，工程師絕不可能開源至 GitHub。
2. **工具鏈封閉與授權昂貴**：Cadence、Synopsys、Mentor 等傳統 EDA 巨頭軟體封閉，缺少輕量 MCP/API 介面，阻礙了開源社群對 Skill 的封裝。
3. **零容錯門禁**：晶片 Tape-out 成本極高，工程師不可能信任純 Prompt 式的生成，必須結合高度嚴謹的 UVM 斷言驗證。
4. **讀者的個人護城河**：正因為公開生態是一片空白，讀者在公司內部利用本機 CLI（ccr / agy）建構閉源的 RTL 比對與 UVM 模組生成器，將形成極具價值的個人效率壁壘。

---

## 方法與限制

本報告結論基於 5,397 筆公開 GitHub Agent Skill 統計資料，解讀時必須誠實面對以下限制：

1. **樣本偏差（Sample Bias）**：資料集僅擷取公開於 GitHub 的受眾。企業內部私有庫、受嚴格監管行業（金融、醫療、晶片 IC 設計、法務）的真實採用率被系統性低估。
2. **分類誤差**：領域（domain）、任務（task）與成熟度（maturity）標籤由 LLM 標註分類，邊界條件可能存在語義識別偏誤。
3. **Star 數非等於實際調用量**：Star 數代表社群可見度與 Repo 流行度，不等於該 Skill 在終端機或 Agent 中的真實執行次數。
4. **Star 歸屬於 Repo 而非 Skill（重要）**：本研究的 star 數是該 skill 所在 repo 的 star，不是 skill 本身的人氣。
   因此「某個 skill 有 23 萬 stars」實際意義是「它被放在一個 23 萬星的大型專案裡」（例如 n8n、flutter、ant-design
   這類主專案順手附了 skill）。引用高星樣本時只能說明「大型專案也開始寫 skill」，**不能當作該 skill 受歡迎的證據**。
5. **每 repo 最多取 6 個 skill**：避免單一大型 skill 集散地灌爆分佈，但這也代表大型 skill 庫的內部多樣性被截斷。
6. **Prompt Injection 威脅**：資料集中包含 87 筆（1.61%）潛在注入疑慮樣本（`injection_suspect`），代表公開生態中存在惡意破壞或越權指令風險，下載開源 Skill 必須審查原始 Markdown/腳本內容。
