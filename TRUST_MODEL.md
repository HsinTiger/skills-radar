# 一個 Skill 該不該裝：判斷流程

## 為什麼這件事比想像中嚴重

Skill 不是「資料」，是**會被 AI 直接當指令執行的檔案**。裝一個 skill ≈ 讓作者在你的 agent 裡下指令，
而 agent 手上有你的檔案系統、git 權限、API 金鑰、瀏覽器登入狀態。

實際被驗證過的攻擊面（2026 年上半）：

| 攻擊手法 | 說明 |
|---|---|
| Prompt injection | SKILL.md 裡藏指令，誘導 agent 洩漏內容或執行動作 |
| 混淆資料外洩 | Base64 / Unicode 隱藏的指令竊取憑證 |
| 外部惡意軟體分發 | 密碼保護的 ZIP、遠端執行腳本 |
| 安全機制停用 | 改系統檔、加後門、越獄 |
| Config injection | 惡意 repo 注入 `.claude/settings.json` 的 hooks，agent 一啟動就執行任意 shell |

Snyk 掃描 3,984 個公開 skill 的結果：**36.82% 有安全缺陷、13.4% critical、76 個確認惡意負載**，
其中 **100% 的惡意 skill 帶惡意程式碼、91% 同時用 prompt injection** — 傳統程式碼掃描擋不住這種複合手法。

發布門檻有多低：一個 SKILL.md + 一個註冊滿一週的 GitHub 帳號，**沒有程式碼簽章、沒有安全審查、預設沒有沙箱**。

## 信任分級

| 級別 | 定義 | 預設處置 |
|---|---|---|
| **T1** | Anthropic 官方（`anthropics/*`）、或你自己寫的 | 可裝，仍建議看過內容 |
| **T2** | 具名維護者、repo 有歷史與社群審視、原始碼可讀且你讀得懂 | 讀完全文再裝 |
| **T3** | 社群清單收錄但無法驗證作者、新帳號、star 暴衝 | **預設不裝** |
| **T4** | 要求金鑰、連外部 endpoint、含混淆內容、附二進位檔 | **不要碰** |

星星數不是背書。惡意 skill 靠的就是刷 star 與掛在精選清單上取得信任。

## 安裝前檢查清單

1. **讀完 SKILL.md 全文**，不是只讀 description。看不懂就不要裝。
2. **搜尋可疑指令模式**：
   ```bash
   grep -rIEn "curl|wget|base64|eval|exec|~/.ssh|\.env|token|secret|api[_-]?key|settings\.json" <skill-dir>
   ```
3. **檢查有無隱藏字元**（Unicode 隱寫是已知手法）：
   ```bash
   perl -ne 'print "$.: $_" if /[\x{200B}-\x{200F}\x{202A}-\x{202E}\x{2060}-\x{206F}\x{E0000}-\x{E007F}]/' <skill-dir>/SKILL.md
   ```
4. **看它有沒有動 config**：任何要改 `.claude/settings.json`、hooks、permissions 的，直接拒絕。
5. **查作者**：帳號年齡、其他專案、是否有人實際 review 過。新帳號 + 單一 repo = 高風險。
6. **生態掃描工具**（第三方，自行評估）：`uvx mcp-scan@latest --skills`
7. **先在隔離環境跑**：新開一個沒有金鑰、沒有重要 repo 的目錄試，別直接在主工作區裝。

## 裝了之後

- 定期重掃：skill 會更新，今天乾淨不代表下次 pull 之後乾淨。**釘住版本**比追最新安全。
- 出現「agent 做了你沒要求的事」→ 立刻停用最近裝的 skill，輪換可能外洩的憑證。
- 你自己的 `.claude/settings.json` 應納入版控，任何非你所為的變動都要能被 diff 出來。

## 爆炸半徑：先算清楚你的 agent 手上有什麼

裝 skill 之前先問自己：這個 agent 現在能碰到什麼？典型的重度使用者手上會有
git push 權限、對外發文管線、瀏覽器的已登入 session、以及各種 API 金鑰。
這組合的爆炸半徑遠大於一般使用者 —— 一個惡意 skill 可以直接用你的身分發文、推 code、
讀取登入後才看得到的頁面。

因此本 radar 的預設立場是：**除非 T1/T2 且你親自讀過，否則不裝**。
