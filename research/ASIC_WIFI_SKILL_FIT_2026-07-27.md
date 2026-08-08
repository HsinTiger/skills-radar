# WiFi ASIC RTL / EDA Skill 適用性研究（2026-07-27）

## 決策摘要

目前公開語料裡，真正貼近 WiFi baseband ASIC RTL 的 skill 是明顯缺口。舊 snapshot 通過
`hardware-eda` 領域與信心閘門後有 847 列，內容去重為 496 個候選；其中 296 個因 FPGA、
embedded、board/PCB、analog/RF 等原因排除，只有 11 個規則式候選被路由為 ASIC 直接用途。
出現 WiFi 詞彙的 43 個候選全部是 embedded/firmware 類，沒有一個通過 WiFi baseband RTL scope。

這些是 `PROVISIONAL_STALE_SNAPSHOT` 的**候選集合內計數**，不是生態比例，也不能推論公開世界
沒有 WiFi ASIC skill。canonical corpus 尚未刷新，secondary taxonomy 也還沒有 LLM golden labels，
所以目前唯一可做的安全決策是：先採用 2 個 evidence-oriented 程序模板，暫不安裝任何第三方 skill。

## Claim / Evidence / Risk

| 狀態 | Claim | Evidence | Risk |
|---|---|---|---|
| `PROVEN` | 新分類已排除 FPGA、embedded、board/PCB、analog/RF | `bin/asic_taxonomy.py`；完整測試套件 30 tests PASS | 規則式次分類仍可能誤標，不能取代 golden labels |
| `PROVEN` | current Release master 比 tracked model report 舊 | master 為 5,937 seeds / 35,293 model rows；report 預期 6,547 / 34,683 | 不得用這份 master 重建母體趨勢 |
| `PROVEN` | 舊 WiFi 採集主要抓到 firmware/ESP 類而非 PHY RTL | provisional catalog 的 43 個 WiFi 候選全部為 `owner_fit=exclude` | 只反映目前 snapshot 與舊搜尋詞 |
| `PROVEN` | `x-npi` 與 OpenADA synthesis skill 有清楚 evidence boundary | 已逐字讀 pinned `SKILL.md`，並檢查依賴、license、commit verification | 尚未在本地商用 EDA runtime 執行 |
| `BLOCKED` | secondary taxonomy 尚未能升格為 validated catalog | `n_golden=0`，evaluation gate 為 `BLOCKED` | 任何 A/B/C/D 都只是候選路由與 source review |

## 「上線率」到底是什麼

本專案的「上線率」是描述性 proxy：

```text
上線率 = maturity 被分類為 production 的 skill 數
       / 該分析範圍內通過 maturity eligibility 的 skill 數
```

`production` 只表示公開描述裡出現錯誤處理、驗證或正式工作流特徵。它**不表示**有真實使用者、
通過 ASIC EDA、可直接進產品 RTL、已被安全審查，或正確性已證明。母體趨勢只能用 neutral sample；
所有 `targeted-*` 只能分析主題內部結構。model label 還必須通過欄位專屬信心門檻。

## 新 taxonomy

| 軸 | 主要值 | Owner 用途 |
|---|---|---|
| `hardware_target` | asic / fpga / embedded / board-pcb / analog-rf / physical / mixed / generic | 先切掉不相關硬體 |
| `asic_stages` | spec、fixed-point、microarchitecture、RTL、lint/CDC/RDC、formal、simulation、UVM、synthesis/STA/power、integration | 對應 RTL lifecycle |
| `wifi_areas` | PHY/baseband、OFDM、MIMO/BF、sync/CFO、channel estimation/equalization、coding/demapper、MAC、RF | 找 WiFi baseband 交集；RF 排除 |
| `owner_fit` | direct / supporting / adjacent / exclude | 決定後續審查與引用方式 |

regex 只在已通過 `hardware-eda` domain gate 的資料內做次分層；sampling query term 不得成為分類
evidence。新的 `asic` 與 `wifi-asic` 採集詞也不含 FPGA、Vivado、firmware、PCB、antenna/RF。

## 逐項 EDA skill 審查

分級代表「可否抽取程序」，不代表可直接安裝或已通過 EDA。

### A — 可直接抽取並改編

| Skill（pinned source） | 適用點 | 為何值得用 | 尚未通過的 gate |
|---|---|---|---|
| [x-npi](https://github.com/BLANK2077/xverif/blob/abc390cc7799ff8075b23d9c25ccf21bbc279e11/skills/x-npi/SKILL.md) | FSDB、APB/AXI/valid-ready、coverage、driver/load 批次分析 | 同一 clock edge 取樣、streaming、大型結果只輸出 JSON 摘要、coverage 用 covered/coverable、遇到不確定 API 先讀 installed pynpi | commit unsigned；真實 pynpi/FSDB 測試未在本機執行；需防內部 signal/license 外洩 |
| [OpenADA synthesis assessment](https://github.com/simra-tech/OpenADA/blob/92895d8f7f6150c9332e51642cfb2b08ccf1886d/skills/assess-synthesis-and-inference/SKILL.md) | synthesis manifest、artifact provenance、false-PASS boundary | 明確區分 execution 與 engineering status；mapped netlist 不等於 equivalence、timing、power 或 silicon correctness | commit unsigned；OpenADA runtime 未驗證；需轉譯到現有商用工具與內部 evidence schema |

兩者都應只抽取方法：前者適合建立 `fsdb-batch-analysis`，後者適合建立 `rtl-synthesis-evidence`。
不要把公開命令、工具路徑或 license 設定直接複製到內部環境。

### B — Supporting procedure

| Skill | 可抽取部分 | 不應照搬部分 |
|---|---|---|
| [Bedrock write-sim-testbench](https://github.com/xlsynth/bedrock-rtl/blob/33720f657d214e96826144d13d223e0a6534bae1/.codex/skills/write-sim-testbench/SKILL.md) | bounded wait、每筆 transaction 的 payload integrity、scoreboard、parameter coverage、narrow waiver | Bazel target、Bedrock helper、Verilator 結果不能代替商用 simulator proof |
| [digital-front-end-skill](https://github.com/kh7272723-star/digital-front-end-skill/blob/92c9780c71639123eae2709683643d4d2d22004e/SKILL.md) | cycle contract、trace-before-code、claim ledger、false-pass audit | 超大 skill 與大量未審 references/scripts；repository 無已識別 license；Icarus gate 不等於產品 EDA |
| [RTL property inference](https://github.com/ArabelaTso/Skills-4-SE/blob/3ec09ea2bbf8b8626aea4e1bdd769de66b0adc35/skills/rtl-property-inference/SKILL.md) | assert/assume/cover 分離、vacuity cover、property confidence | 從現有 RTL 推 intent 會複製原 bug；liveness/fairness 必須由 spec owner 確認；候選 property 不等於 proof |

### C — 只作參考

- `logic-synthesis`：stage inventory 可參考，但 blanket false-path、clock uncertainty rule-of-thumb、
  project-memory write 與 orchestrator 依賴，不可進 golden flow。
- `rtl-specification-consistency-checker`：可借 requirement matrix；純閱讀不能標成 satisfied/PASS。
- `assertion-design`：檔案分離與命名可借；部分 SVA/AXI 例子需 syntax 與 normative review。
- `eda-sim`：VCS/FSDB 題目相關，但含固定 license topology、`.envrc` 建立與 `$finish`/grep 弱門禁。
- `rtl-repair`：root-cause grouping 可借；mental re-check、format compliance 與自動 RTL mutation 不可接受。
- `run-vcs`：post-layout、固定目錄與 background `nohup`，不屬目前 RTL 主軸。
- `rtl-p4-implement` / `rtl-p5s-sva-check`：只是大型 agent bundle 的 router，無法獨立引用。

### D — 明確排除

FPGA/Vivado/Quartus/bitstream、MCU/firmware/ESP、board/PCB、analog/RF/antenna skill 全部排除。
即使描述同時出現 SystemVerilog 或 WiFi，也不因關鍵字重疊而升級。

## 接下來的 RTL 如何引用 skill

第三方 skill 只能是 procedure source，不是工程 authority。建議流程：

```text
pin source commit
  -> read-only security/license/dependency review
  -> extract one bounded procedure
  -> owner approve
  -> rewrite as internal deterministic adapter
  -> secure runtime execute
  -> collect compile/elab/sim/formal/synthesis evidence
  -> persist skill_usage manifest
```

每次 RTL 任務至少保存：

```yaml
skill_usage:
  source_repo: BLANK2077/xverif
  source_commit: abc390cc7799ff8075b23d9c25ccf21bbc279e11
  source_path: skills/x-npi/SKILL.md
  extracted_procedure: fsdb-clock-edge-protocol-summary
  local_adapter_revision: <internal git sha>
  owner_approval: <decision id>
  inputs_sha256: [<rtl/spec/flist hashes>]
  tool_identity: <product/version>
  commands: [<approved deterministic commands>]
  evidence_artifacts: [<log/report/json hashes>]
  claims:
    compile: PASS|FAIL|UNKNOWN
    elaboration: PASS|FAIL|UNKNOWN
    simulation: PASS|FAIL|UNKNOWN
    formal: PASS|FAIL|UNKNOWN|NOT_RUN
    synthesis: PASS|FAIL|UNKNOWN|NOT_RUN
```

PASS 不可向上偷渡：syntax/lint PASS 不等於 compile；compile 不等於 elaboration；simulation test PASS
不等於完整 spec；synthesis/mapping PASS 不等於 LEC、STA、power、physical 或 silicon PASS。

## 知識庫目前顯示的趨勢

1. 公開 hardware skill 的噪音主要來自 embedded 與 FPGA，不是 ASIC front-end；repo star 也不能修正這個偏差。
2. 真正可重用的價值集中在 evidence capture、reproducibility、bounded verification，而不是一鍵產 RTL。
3. EDA skill 常把「命令成功、log 有 `$finish`、格式 compliance PASS」誤升格成工程 PASS；最好的 skill 會明確列出未證明事項。
4. WiFi baseband ASIC skill 在目前公開 snapshot 是 coverage hole；需要新的 `wifi-asic` 採集與人工 golden labeling，不能用舊 WiFi 結果回答。
5. 第三方 skill 與內部 RTL 之間需要 deterministic adapter 與 evidence manifest，不能直接安裝即用。

## Kanban summary

| 狀態 | 工作項 | Exit criterion |
|---|---|---|
| Done | narrowed `asic` / `wifi-asic` harvest topics | 不含 FPGA、embedded、PCB、RF 搜尋詞 |
| Done | 多軸 taxonomy、strict merge、catalog、evaluation gate | 單元測試通過；stale/golden 缺口顯式 BLOCKED |
| Done | 13 個高相關來源逐讀與 commit pinning | A/B/C decision 有 dependency、risk、evidence |
| Blocked | canonical corpus refresh | master 與 model report 對齊為 6,547 / 34,683 |
| Next | 執行新採集並做至少 200 個 stratified golden labels | target/fit accuracy ≥ 0.75；multi-label Jaccard ≥ 0.65 |
| Next | 內部 pilot：`fsdb-batch-analysis` | 一個非機密 canary、readback、artifact hash、owner acceptance |
| Next | 內部 pilot：`rtl-synthesis-evidence` | 現有 golden flow 對照，不能新增 false PASS |

Owner watch item：先批准「只抽取 x-npi/OpenADA 方法」或指定另一個 pilot；在 golden-label 與 runtime
evidence 完成前，不把任何第三方 skill 列為已上線。
