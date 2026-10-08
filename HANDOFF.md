# 交接：每日 routine 從 Mac 移出

**2026-10-08 起，Mac 本機的 launchd 排程已關閉。** 這條每日 routine 現在沒有任何機器在跑，
等接手的機器設定完成才會恢復。

接手前請先讀 `CLAUDE.md`（安全規則，特別是語料的部分），再讀這一頁。

---

## 現況

| 項目 | 值 |
|---|---|
| 線上看板最後更新 | **2026-08-09** |
| 語料（本機與 Release 一致） | **45,612 筆** |
| GitHub Actions freshness watchdog | **連續紅燈約兩個月** |
| Mac launchd | **已 bootout + disable，plist 已移走** |

## 為什麼停的（請不要重蹈）

2026-08-12 有一次手動補跑，結束時 `data/` 底下三個檔沒有 commit。
隔天起 `bin/run_daily.sh` 的前置檢查就一直擋：

```
STOP: worktree 在每日流程開始前不是 clean；拒絕自動 stage
```

**連續擋了 54 次（08-13 ~ 10-08），完全沒有產出。**

兩個教訓，兩個都不是程式的錯：

1. **在這個 repo 動手而不收尾，會讓隔天的排程整條停掉。** 檢查本身是對的——
   它拒絕把不明來源的改動自動 stage 進每日 commit。手動跑完一定要 commit 乾淨。
2. **告警管道必須被驗證過。** watchdog 每天都在紅燈，機制完全正確，但沒有人看到。
   這已經是這個專案第二次因為同一個原因失明（第一次是 2026-07-29 ~ 08-07）。
   **接手的第一件事應該是把 watchdog 失敗接到你真的會看到的地方。**

---

## 接手機器要做的事

### 一次性設定

```bash
git clone https://github.com/HsinTiger/skills-radar.git
cd skills-radar

# 語料不在 git 裡（太大），從 rolling Release 取
gh release download corpus-latest --pattern master.jsonl.gz --dir corpus --clobber
gunzip -f corpus/master.jsonl.gz

python3 -m pip install -r requirements-ml.txt
python3 -m unittest discover -s tests        # 應該 121 passed
python3 bin/check_privacy.py
```

需要的外部指令：`gh`（已登入且有 push 權限）、`python3`、以及 `agy` 或 `claude` 其中一個。

### 排程

每日 **08:30 Asia/Taipei** 執行 `bin/run_daily.sh`，並把環境變數設成你的排程器種類：

```
SKILLS_RADAR_RUN_CONTEXT=schtasks    # Windows 工作排程器
SKILLS_RADAR_RUN_CONTEXT=cron        # cron
SKILLS_RADAR_RUN_CONTEXT=systemd     # systemd timer
SKILLS_RADAR_RUN_CONTEXT=github-actions
```

**不要用 `manual`。** `bin/check_published_freshness.py` 會擋下來——那條檢查的用意是
「證明這次是排程觸發的，不是人手動跑的」。白名單在 `SCHEDULER_CONTEXTS`，
要新增排程器種類就加在那裡（2026-10-08 之前這裡寫死 `launchd`，已改掉）。

`bin/install_launchd.sh` 與 `bin/check_launchd.sh` 是 macOS 專用，接手機器不需要用。

### 怎麼確認真的成功

本機所有 gate 通過**不代表發佈成功**。要跑遠端回讀：

```bash
python3 bin/check_published_freshness.py     # exit 0 才算數
```

它會抓 live Pages 的 `pipeline_health.json`，比對日期、gates、以及 execution_context。

---

## 每天實際會發生什麼

`bin/run_daily.sh` 依序做：`git pull --ff-only` → 抓事實 → AI 產每日簡報 → 稽核 →
`bin/daily_research.sh`（增量採集／分類／聚合／四尺度摘要／每日觀點／專區／建站）→
重建 README → 發 Release 快照 → commit → push。

**整條是 fail-closed 的**：任何一步失敗就停，不會發佈半套。LLM 只在三個地方用到
（每日簡報、四尺度摘要、每日觀點），其餘全部零 token。

四個尺度（日／週／月／季）各自獨立 cadence，只更新「上一個完整期」，
離線後依 `period_id` 補跑缺期、不重算已成功的期。補跑會把所有缺期**打包成一次 AI 呼叫**，
所以停很久再開機不會爆成本。

---

## 已知地雷

| 地雷 | 說明 |
|---|---|
| **worktree 不 clean** | 整條流程會停。手動跑完務必 commit。 |
| **本機有未推的 commit** | `git pull --ff-only` 會失敗，隔天起整條停。做完當天就推。 |
| **`seen.tsv` 與 master 脫節** | 換過 `corpus/master.jsonl` 之後，要用 master 的 `repo`+`path` 補回 `corpus/seen.tsv`，否則會重抓並產生 duplicate 被擋下。 |
| **Python 版本** | Mac 上是 3.9，所以程式碼避開了 3.10+ 的 runtime 語法（例如 `Path.write_text(newline=)`）。接手機器若是 3.11+ 不受影響，但**請維持相容**，Mac 可能還會回來跑。 |
| **`agy` 不吃 cwd** | 用 `agy` 當 provider 時必須帶 `--add-dir`，否則它會把檔案寫到自己的 scratch 目錄，而且回報「已建立」。靜默失敗。 |
| **GitHub code search 速率** | 實測上限是 10 次/分鐘（不是 30），節流設 6.5s。 |
| **雙機同時寫** | 同一時刻只能有一台在跑。接手後請確認 Mac 這邊確實是關的。 |

## 發佈前的閘門（會擋，不要繞過）

```
bin/check_privacy.py              雇主名稱與持倉資訊
bin/validate_publish_scope.py     每日自動 commit 只能碰白名單路徑
bin/security_gate.py verify       語料進模型前的隔離
bin/wiki_lint.py                  跨報告數字矛盾
```

注意 `validate_publish_scope.py` 失敗時回傳 **2**。
**不要把它 pipe 到 `tail` 之類的東西**，pipeline 的 exit code 會取最後一個指令，把 2 吃掉。

## 安全邊界

`corpus/*.jsonl` 是陌生人寫的、本來就設計成要被 AI 當指令讀的文字，約 1.36% 命中疑似惡意樣態。
**不要把原始語料餵給有工具權限的 agent。** 完整規則在 `CLAUDE.md`，動手前請先讀。

分類路徑目前是安全的：`bin/classify.sh` 用 `--tools ""`（模型完全沒有工具）
加 `--no-session-persistence` 加預算上限，最壞情況被限制在「標錯標籤」。
**新增任何模型呼叫都要維持這三個條件。**

## 交接紀錄

歷史寫在 `MAC_AGENT_WORKLOG.md`。接手後有事請寫在那裡，Mac 這邊看得到。
