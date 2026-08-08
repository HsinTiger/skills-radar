# RTL Front-end Skill Deep Dive：先建證據核心，再讓 AI 寫 RTL

> 日期：2026-07-28  
> 範圍：WiFi baseband ASIC front-end  
> `NX_CONTEXT=SNAPSHOT_ONLY`：已用 OA 知識與獲准的 NX delivery snapshot 校準方向，但沒有當前 NX canonical runtime 或產品 RTL 證據。

## 今天的觀點

GitHub 搜尋 `RTL design skill`，不難找到會產生 SystemVerilog 的 agent。真正稀缺的卻不是「把文字變成 RTL」；
稀缺的是一套能回答下列問題、而且答案可重跑的控制面：需求是否已凍結？fixed-point 的 signedness、bit growth、
rounding、saturation 與 reset boundary 是誰決定的？filelist、define、generated source、clock 與 waiver 是否完整？
工具到底比較了幾個 points？一個綠色 PASS 是功能、語法、lint、CDC、formal、synthesis，還是只是 command exit 0？

這也是本輪研究後最大的排序修正：**先建立 evidence kernel，再建立 RTL generator。**

若 generator 先上線，AI 只會更快地製造需要工程師重新猜 intent、重新翻波形、重新跑 LEC 的候選 patch。
反過來，若先把 intent、claim boundary、artifact provenance 與 fail-closed gate 固化，同一套底座不只服務 RTL
生成，也能服務 architecture review、CDC/RDC、formal、debug、synthesis 與 frontend ECO。對你的工作而言，這比
追求「一鍵 RTL」更接近真正可複用的 ASIC design automation。

## 研究邊界

主力範圍：

- spec、algorithm/fixed-point intent、microarchitecture；
- synthesizable SystemVerilog RTL、review、minimal-diff fix；
- lint、CDC、RDC、SVA、formal；
- VCS compile/elaboration/simulation 與 Verdi/FSDB debug；
- 邊界只到 logic synthesis、Formality/Conformal LEC、pre/post frontend ECO。

明確排除：FPGA／Vivado／Quartus、MCU／firmware、PCB、analog/RF，以及 floorplan、P&R、CTS、route、
physical signoff、spare-cell/metal-only ECO。

本輪以 GitHub code search 找到 20 個新候選；10 個完成 pinned `SKILL.md` 深評，另對 3 個容易誤用的候選做
明確降級或排除。`commit_verified=true` 只表示 HEAD 與 raw source readback 對得上，不代表 signed commit，
更不代表 skill 正確。沒有執行任何第三方 skill/script。

## 建議採用順序

| 順序 | 內部能力 | 優先抽取的公開 skill | 為什麼先做 | 真正升級 claim 的 gate |
|---:|---|---|---|---|
| 1 | RTL architecture/evidence governor | [OpenADA review-rtl-architecture](https://github.com/simra-tech/OpenADA/blob/939fe803882956b9e6c34e0270f82ba8bbdfe991/skills/review-rtl-architecture/SKILL.md) | 把 filelist、top、defines、clock/reset、protocol intent 與各種 claim 拆開 | 真 parser/lint/elaboration/CDC/formal/synthesis evidence |
| 2 | frozen spec + fixed-point contract | [learner-ran spec-planner](https://github.com/learner-ran/agent-for-ic-design/blob/44252fcfb97c67fd4d8e02f0266d3bbd6e142d8e/.agents/skills/spec-planner/SKILL.md) | 最貼近 bit growth、rounding、saturation、valid-ready、counter terminal 與 reset 語意 | owner-approved intent artifact + bit-true oracle |
| 3 | uArch traceability | [rtl-p3-uarch-policy](https://github.com/babyworm/rtl-agent-team/blob/ca43e220af36492be516996b137dafb1922c2d88/skills/rtl-p3-uarch-policy/SKILL.md) | REQ→block→clock/protocol/storage/FSM 的反向追蹤與 throughput invariant | 可重現 BFM/reference-model canary |
| 4 | read-only RTL second pass | [rtl-quality-reviewer](https://github.com/learner-ran/agent-for-ic-design/blob/44252fcfb97c67fd4d8e02f0266d3bbd6e142d8e/.agents/skills/rtl-quality-reviewer/SKILL.md) | 先抓 signedness、width、reset、protocol 與 tool/coverage gap，不直接改 RTL | finding 綁 requirement ID、file/signal/trigger 與 evidence hash |
| 5 | CDC/RDC claim boundary | [hw-cdc](https://github.com/nlsundeep/Hardware-Design-Agent-Workflow/blob/5a53e85f43337872a6dc19817a6234b27f258b00/.claude/skills/hw-cdc/SKILL.md) | structural review 永遠只能是 PARTIAL，且要求 crossing inventory/domain-map delta | 真 CDC/RDC tool report、waiver 與 reconvergence review |
| 6 | earliest-divergence debug | [systemverilog-waveform-debug](https://github.com/L1Ban404-computer-architecture/systemverilog-waveform-debug-skill/blob/3af2c119a59d2a1ffaef0774c0e2de52bc990e3b/SKILL.md) | Observed/Inferred/Hypothesis 分離，一次只驗一個 falsifiable hypothesis | VCS/Verdi/FSDB readback；不可只靠離線 VCD 敘述 |
| 7 | formal property lifecycle | [formal-verification](https://github.com/chuanseng-ng/digital-chip-design-agents/blob/d9ec7f93343ecdd7bd7d886ef28563f8c5960308/plugins/formal/skills/formal-verification/SKILL.md) | 把 assert/assume/cover、vacuity、CEX、inconclusive 分開 | 真 formal report + owner-approved assumption/waiver |
| 8 | non-vacuous ECO/LEC gate | [equivalence-check](https://github.com/vibeic/vibe-ic/blob/93ff966d3258ab2b1abc914abf72d9ef72d3648b/vibe-ic-marketplace/plugins/vibe-ic/skills/equivalence-check/SKILL.md) | PASS 必須 `compared-points > 0`，且 non-equiv/unproven/aborted 為零 | Formality/Conformal canonical report readback |
| 9 | behavior-preserving synth prep | [prepare-rtl-for-synth](https://github.com/Emin017/skills/blob/40f7471ee1e4a03a2074e2bd7e336c5c10bde16a/prepare-rtl-for-synth/SKILL.md) | file order、generated source、macro semantics 與 downstream parser 對齊 | VCS/DC/LEC；syntax compatibility 不等於等價或 QoR |
| 10 | guarded RTL authoring | [systemverilog-rtl-generator](https://github.com/learner-ran/agent-for-ic-design/blob/44252fcfb97c67fd4d8e02f0266d3bbd6e142d8e/.agents/skills/systemverilog-rtl-generator/SKILL.md) | approved plan、interface/reset preservation、minimal diff、明確 arithmetic policy | compile/elab/sim/lint；ECO 類 patch 另需 LEC |

這不是安裝清單。A/B 級代表「值得抽取 procedure 並重寫為內部 deterministic adapter」，不是可以把外部 skill
直接指向產品 RTL。

## 每個候選真正能帶走什麼

### 1. OpenADA architecture review：最接近 evidence kernel

它的價值不在 OpenADA 命令，而在把 `execution.status` 與 `engineering.status` 分開，並強迫 reviewer 先凍結
ordered sources、top、include、define、generated source、clock/reset 與 protocol intent。這非常適合成為內部
`wifi-bbdd-rtl-review` 的外殼。

限制也很清楚：公開 contract 對 parameter override、library/waiver provenance 仍不完整；clean lint 不能證明功能。
因此採用方式應是保留 schema 與 claim boundary，將實際命令完全換成已核准的 parser、lint、VCS、CDC、formal
與 DC flow。

### 2. spec-planner + uArch policy：目前最好的 fixed-point 前置組合

目前沒有一個公開 skill 同時懂 WiFi baseband、bit-true arithmetic 與你的內部設計慣例。較安全的組合是：

- 用 `spec-planner` 強制 signedness、bit growth、truncation、rounding、saturation/wrap、counter terminal、
  valid-ready fire/stall 與 reset semantics；
- 用 `rtl-p3-uarch-policy` 補 REQ→uArch trace、throughput invariant、clock/protocol/storage allocation 與
  reference-model/BFM gate；
- 拒絕後者固定的 SRAM/buffering threshold、命名與多 agent topology，因為它們不是跨技術與跨 block 的真理。

這兩個 skill 的交集，才是你的 `fixed-point-bittrue-contract` 雛形。

### 3. RTL reviewer 與 generator：必須分權

`rtl-quality-reviewer` 預設 read-only，適合當獨立 second pass；`systemverilog-rtl-generator` 則只在 frozen spec 與
approved plan 後產生 candidate patch。兩者不應由同一個 agent 在同一輪同時「寫、審、宣告 PASS」。

最小接受鏈應是：

```text
owner-approved intent
  -> candidate RTL/minimal ECO
  -> independent RTL review
  -> compile + elaboration
  -> simulation/formal/CDC as applicable
  -> synthesis
  -> pre/post-ECO LEC when semantics may change
```

TB 不得為了迎合 candidate RTL 而改；沒有 tool artifact 就只能是 `NOT_RUN` 或 `UNKNOWN`。

### 4. CDC/RDC：公開 checklist 的價值是阻止 false PASS

`hw-cdc` 最值得留下的是「structural-only review 最大只能標 PARTIAL」，以及 per-crossing inventory、domain-map delta、
pulse/bus/handshake/FIFO/reconvergence、RDC 分開處理。它不能取代 CDC tool，卻能阻止「看到兩級 FF 就宣布安全」。

反例也很有教育意義：[Gateflow `sv-design`](https://github.com/codejunkie99/gateflow-cli/blob/339c75023186d738f330510a45dbbb50b8b19467/packages/claude-plugin/skills/sv-design/SKILL.md)
對多 bit CDC 給出 WIDTH>1 的 2FF template；各 bit 獨立同步可能形成 incoherent word，因此列為 D、明確排除。

### 5. 波形 debug：方法是 A，介面仍需重做

`systemverilog-waveform-debug` 的 provenance、scope discovery、X/Z 保留、bounded probe、earliest divergence 與
falsifier 都很成熟；但它原生面向 VCD/FST，沒有直接處理 FSDB。對你的路線，應保留方法、重做介面：
由內部 VCS/Verdi adapter 輸出獲准的 bounded readback，再讓 agent 解釋。沒有 simulator scheduling-region 證據時，
離線波形不得宣稱 race root cause 已證明。

### 6. LEC：frontend ECO 最重要的是「比較有實質」

`equivalence-check` 的核心條件很簡單，但比大量只 grep `PASS` 的 flow 更有價值：`compared-points > 0`，且
non-equivalent、unproven、aborted 都必須為零；report 缺失或解析失敗就 fail closed。這可直接轉成內部
Formality/Conformal parser contract。

[Arabela `rtl-equivalence-checker`](https://github.com/ArabelaTso/Skills-4-SE/blob/0f00a4fc37905ec9d69a3413b51efefd57e9a997/skills/rtl-equivalence-checker/SKILL.md)
只能幫忙整理 diff、改變的 module 與可能的語意風險，評為 C；它不是 LEC。

[Vibe-IC `eco-plan`](https://github.com/vibeic/vibe-ic/blob/93ff966d3258ab2b1abc914abf72d9ef72d3648b/vibe-ic-marketplace/plugins/vibe-ic/skills/eco-plan/SKILL.md)
則是 post-P&R spare-cell/metal-only ECO，與 frontend ECO 同名但不同 realm，評為 D、排除。

## 為你建議的內部 skill suite

第一階段不是十幾個獨立 agent，而是一個共享 evidence kernel 加六個薄 adapter：

```text
wifi-bbdd-intent-contract
  ├─ rtl-architecture-review
  ├─ fixed-point-bittrue-contract
  ├─ vcs-verdi-evidence
  ├─ cdc-rdc-evidence
  ├─ formal-property-evidence
  └─ synthesis-lec-eco-evidence
```

共用 kernel 至少保存：input revision/hash、top/filelist/include/define/generated source、tool/version、clock/reset、
requirement ID、assumption/unknown、command/exit status、artifact hash、denominator、finding、owner disposition 與
每個 claim 的 `PROVEN/ASSUMED/UNKNOWN/BLOCKED/NOT_RUN`。

RTL generator 要放在這些 adapter 之上，並且只能輸出 candidate patch。真正的「知識複利」不是讓 agent 自動
commit，而是讓每次 owner 退件、tool failure、waiver 與 root cause 都回寫成下一次可重用的 contract 或 canary。

## 90 天實作路線

### 0–30 天：evidence kernel + 一個公開 canary

- 建立 `design_intent.schema`：interface、cycle/latency、reset、backpressure、fixed-point、throughput、assumption、unknown；
- 建立 `evidence_manifest.schema`：input hash、tool identity、command、artifact、denominator、claim boundary；
- 用公開 ready/valid fixed-point toy block 驗證另一個 agent 能否只靠 bundle 重建 context；
- 不產產品 RTL、不接自動 commit。

### 31–60 天：接真 front-end readback

- VCS compile/elaboration/simulation 與 Verdi/FSDB bounded query；
- RTL quality second pass；
- CDC/RDC crossing inventory 與 formal property lifecycle；
- 故意注入 signedness、reset、backpressure、multi-bit CDC、vacuous assertion 等失敗 canary，證明 gate 會拒絕。

### 61–90 天：合成、LEC、frontend ECO

- DC synth-prep 與 synthesis evidence 分離；
- Formality/Conformal parser 要求 compared denominator、unproven/aborted/black-box/state-map status；
- 只開放 minimal candidate ECO，並以 pre/post LEC 為必要 gate；
- 連續三個不同 block 可重現後，才把 procedure 升格為公司級 skill。

## 在下一個 RTL 設計中怎麼引用

在內部 skill 尚未建好前，不要寫「請用某 GitHub skill 幫我完成 RTL」。應把外部來源降為 method reference：

```text
先用已核准的 intent contract 凍結 spec、fixed-point、cycle、interface、reset 與 unknown；
參考 pinned OpenADA architecture-review 的 claim 分層方法，但不要執行它的工具命令。
只產生 candidate SystemVerilog patch，不改 TB、不宣稱 PASS。
交付 requirement trace、minimal diff、compile/elab/sim/CDC/formal/synthesis/LEC 的 NOT_RUN 或 artifact evidence。
任何 blocking ambiguity 停在 owner gate。
```

每次引用都要記錄 source repo/path/commit、抽取的 procedure、本地 adapter revision、owner approval、input hash、
tool identity、artifact hash 與未執行的 gates。這樣換模型、換 agent，流程真相仍留在 durable contract 裡。

## Kanban summary

| 狀態 | 工作 | Exit criterion |
|---|---|---|
| Done | 前端範圍收斂 | EDA 專區排除 FPGA、physical design；邊界只到 synthesis/LEC/frontend ECO |
| Done | 20 個新候選搜尋、10 個 pinned 深評、3 個降級/排除 | commit/path/license、fit、evidence、risk、decision 可回讀 |
| Done | taxonomy 與排序改為 architecture/fixed-point/RTL 優先 | 同 grade 下 frontend architecture 高於 simulation 與 synthesis |
| Blocked | 第三方 skill 的產品可用性 | 尚無 NX VCS/Verdi/DC/Formality runtime proof；`NX_CONTEXT=SNAPSHOT_ONLY` |
| Blocked | unattended 每日更新 | 2026-07-28 是 manual recovery；需 2026-07-29 08:30 `execution_context=launchd` |
| Next | 建立 evidence kernel schema 與公開 canary | 正常與 intentional-failure 都有 deterministic artifact/readback |
| Next | 接 VCS/Verdi，再接 CDC/formal/DC/LEC | 每個 gate 分開、fail closed、不可互相替代 |
| Owner-watch | 是否核准第一個內部 pilot | 建議先做 `rtl-architecture-review + fixed-point-bittrue-contract`，不要先做 generator |

最後的限制要說白：目前仍沒有一個可直接安裝、真正懂 WiFi baseband ASIC 的公開 skill。公開世界提供的是
procedure pattern；WiFi algorithm、bit-true oracle、golden flow、waiver 與 signoff authority 仍必須留在受控的內部知識
與真工具證據中。
