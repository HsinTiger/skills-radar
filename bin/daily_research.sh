#!/bin/bash
# 每日研究增量：可稽核、fail-closed 版
#
# 成本分配（重點）：
#   零 token   ── 採集(update_corpus) / 聚合(aggregate) / 機會訊號(opportunity) / evidence gate
#   少量 token ── 只分類「新增的」skill（穩定後每天幾十筆，非 5,400 筆）
#   一次 token ── 每日觀點文章（輸入是受 citation contract 約束的 evidence ledger）
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
LOG="$ROOT/data/research.log"
export TZ="Asia/Taipei"
DATE=$(date +%Y-%m-%d)
log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }
log "=== research start $DATE ==="

# 0. GitHub CLI 是 collector 的必要依賴。launchd 的 PATH 或 auth 不完整時必須在
# 改動 corpus 前停止，不能把 FileNotFoundError 誤報成「零新增」。
if ! command -v gh >> "$LOG" 2>&1; then
  log "STOP: GitHub CLI (gh) 不在 PATH；請重載版本化 LaunchAgent"
  exit 1
fi
if ! gh auth status >> "$LOG" 2>&1; then
  log "STOP: gh auth status 失敗；未開始 corpus collector"
  exit 1
fi

# 1. 增量採集（零 token）。wrapper 會把 FAILED、有效零增量與真實新增分開，
# 並將 master readback 寫入 data/corpus_update_manifest.json。
if ! DELTA=$(python3 bin/update_corpus.py --date "$DATE" 2>>"$LOG"); then
  log "STOP: corpus collector 失敗；不得宣稱今日零新增"
  exit 1
fi
if [ -n "$DELTA" ] && [ -s "$DELTA" ]; then
  NEW=$(wc -l < "$DELTA" | tr -d ' ')
  log "新增 $NEW 筆"
  # 2. LLM 只作有上限的種子標註；異常大批次交給既有 6k+ 種子訓練的本機模型，
  # 並由 field-confidence gate 排除低信心列，避免無上限 token 成本成為排程單點失敗。
  MAX_LLM_DELTA=${SKILLS_RADAR_MAX_LLM_DELTA:-180}
  if [ "$NEW" -le "$MAX_LLM_DELTA" ]; then
    CLASSIFY_MAX_BUDGET_USD=${CLASSIFY_MAX_BUDGET_USD:-0.60} \
      ./bin/classify.sh "$DELTA" 45 4 >> "$LOG" 2>&1 || {
      log "STOP: 新增 skill LLM 種子分類失敗；不得部分 merge"; exit 1;
    }
    python3 bin/merge_classified.py "$DELTA" >> "$LOG" 2>&1 || {
      log "STOP: 新增 skill merge 失敗；不得繼續訓練或發佈"; exit 1;
    }
  else
    log "新增 $NEW 筆超過 LLM seed 上限 $MAX_LLM_DELTA；使用本機模型並保留 confidence gate"
  fi
else
  NEW=0
  log "collector 成功，今日為有效零增量"
fi

# 2.5 本機分類器：用 LLM 種子標註訓練，替新樣本標籤（零 token）
python3 bin/train_classifier.py >> "$LOG" 2>&1 || {
  log "STOP: 分類器訓練或 model/master alignment 失敗"; exit 1;
}

# 2.6 每週一重新分群，發現既有分類法沒涵蓋的新用法（零 token）
if [ "$(date +%u)" = "1" ]; then
  python3 bin/cluster.py 120 >> "$LOG" 2>&1 || log "WARN: 分群失敗"
fi

# 2.7 惡意內容掃描（零 token）——這個專案的本質是大量讀取陌生人寫的、會被 AI 當指令的文字
python3 bin/scan_injection.py >> "$LOG" 2>&1 || log "WARN: 注入掃描失敗"

# 3. 聚合 + 機會訊號（零 token）
python3 bin/aggregate.py >> "$LOG" 2>&1 || {
  log "STOP: aggregate 失敗，不使用舊訊號表繼續"; exit 1;
}
python3 bin/opportunity.py >> "$LOG" 2>&1 || {
  log "STOP: opportunity 失敗，不使用舊訊號表繼續"; exit 1;
}

# 3.5 每日 owner-facing 建議清單（零 token）
# EDA/IC 只引用已審來源；財經類只允許研究用途，交易／credential 風險會降級或排除。
python3 bin/build_daily_recommendations.py --date "$DATE" >> "$LOG" 2>&1 || {
  log "STOP: 每日 skill 建議清單產生失敗"; exit 1;
}

# 3.6 各尺度獨立 cadence dispatcher（零 token evidence + due period 才用 AI）
# 日/週/月/季只更新上一個完整期；依 period_id 補跑，不重算成功期。
python3 bin/timescale_summaries.py --date "$DATE" >> "$LOG" 2>&1 || {
  log "STOP: 多尺度摘要 freshness/evidence gate 失敗"; exit 1;
}

# 4. 每日觀點文章（唯一的研究 LLM 步驟）。先建立來源受限 evidence ledger，
# 再驗收主張、引用、數字與 no-trade boundary，最後安全轉成 HTML。
python3 bin/build_editorial_evidence.py --date "$DATE" >> "$LOG" 2>&1 || {
  log "STOP: editorial evidence gate 失敗"; exit 1;
}
OUT="$ROOT/research/editorials/$DATE.md"
python3 bin/generate_ai_artifact.py editorial --date "$DATE" --output "$OUT" >> "$LOG" 2>&1 || {
  log "FAIL: 每日觀點 AI provider、citation 或結構驗收失敗"; exit 1;
}
python3 bin/render_editorial.py --date "$DATE" >> "$LOG" 2>&1 || {
  log "STOP: 每日觀點 HTML render 失敗"; exit 1;
}
log "每日觀點 ok ($(wc -c < "$OUT") bytes)"
# research/insights/ 保留為 legacy archive，不再每日重複呼叫第二次 AI。

# 4.5 累積式 Domain Wiki ingest（零 token；同日證據變動必須人工附 revision note）
python3 bin/wiki_ingest.py --date "$DATE" >> "$LOG" 2>&1 || {
  log "STOP: Wiki ingest 失敗，避免靜默改寫 evidence history"; exit 1;
}

# 4.6 重建前端頁面（零 token）
python3 bin/build_site.py >> "$LOG" 2>&1 || {
  log "STOP: build_site 失敗，不推送 stale 頁面"; exit 1;
}

# 4.7 跨報告矛盾與 Wiki 結構偵測（零 token）——參考 Karpathy LLM Wiki 的 lint 概念
if ! python3 bin/wiki_lint.py >> "$LOG" 2>&1; then
  log "WARN: 發現跨報告矛盾，需人工判斷是修正舊報告還是說明數字為何改變"
fi

# 4.8 個資閘門：公開 repo，推之前必須確認沒有雇主名稱／持倉資訊
python3 bin/check_privacy.py >> "$LOG" 2>&1 || { log "STOP: 個資檢查未通過，中止本次流程"; exit 1; }

# 5.5 公開 health marker：本機 gate 與 remote publish 證據分開。
python3 bin/write_pipeline_health.py --date "$DATE" --privacy-passed >> "$LOG" 2>&1 || {
  log "STOP: pipeline health 核心 gate 未通過"; exit 1;
}

# health marker 要進入自足式頁面；重建後再跑一次 privacy gate。
python3 bin/build_site.py >> "$LOG" 2>&1 || {
  log "STOP: health marker 寫入後重建頁面失敗"; exit 1;
}
python3 bin/check_privacy.py >> "$LOG" 2>&1 || {
  log "STOP: 最終頁面個資檢查未通過"; exit 1;
}

log "=== research done (新增 $NEW) ==="
