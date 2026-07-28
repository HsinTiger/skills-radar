#!/bin/bash
# 每日研究增量：省 token 版
#
# 成本分配（重點）：
#   零 token   ── 採集(harvest_delta) / 聚合(aggregate) / 機會訊號(opportunity) / 驗證(validate)
#   少量 token ── 只分類「新增的」skill（穩定後每天幾十筆，非 5,400 筆）
#   一次 token ── 洞察專區（輸入是幾 KB 的訊號表，不是原始語料）
set -uo pipefail
ROOT="$HOME/skills-radar"
cd "$ROOT" || exit 1
LOG="$ROOT/data/research.log"
DATE=$(date +%Y-%m-%d)
log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }
log "=== research start $DATE ==="

# 1. 增量採集（零 token）
DELTA=$(python3 bin/harvest_delta.py 2>>"$LOG")
if [ -n "$DELTA" ] && [ -s "$DELTA" ]; then
  NEW=$(wc -l < "$DELTA" | tr -d ' ')
  log "新增 $NEW 筆"
  # 2. 只分類新增的（token 花在這，但量小）
  ./bin/classify.sh "$DELTA" 45 4 >> "$LOG" 2>&1
  python3 bin/merge_classified.py "$DELTA" >> "$LOG" 2>&1
else
  NEW=0
  log "今日無新增 skill"
fi

# 2.5 本機分類器：用 LLM 種子標註訓練，替新樣本標籤（零 token）
python3 bin/train_classifier.py >> "$LOG" 2>&1 || log "WARN: 分類器訓練失敗"

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

# 4. 洞察專區（唯一的 LLM 步驟，輸入只有訊號表）
OUT="$ROOT/research/insights/$DATE.md"
python3 bin/generate_ai_artifact.py insight --date "$DATE" --output "$OUT" >> "$LOG" 2>&1 || {
  log "FAIL: 洞察專區 AI provider 或結構驗收失敗"; exit 1;
}
log "洞察專區 ok ($(wc -c < "$OUT") bytes)"

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

# 5. 稽核（零 token）：數字必須回溯得到訊號表
python3 bin/validate_research.py "$DATE" >> "$LOG" 2>&1 || log "WARN: 稽核有異常，見 log"

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
