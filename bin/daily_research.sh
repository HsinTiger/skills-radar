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
python3 bin/aggregate.py >> "$LOG" 2>&1
python3 bin/opportunity.py >> "$LOG" 2>&1

# 4. 洞察專區（唯一的 LLM 步驟，輸入只有訊號表）
OUT="$ROOT/research/insights/$DATE.md"
mkdir -p "$ROOT/research/insights"
TMP=$(mktemp)
{ sed "s/YYYY-MM-DD/$DATE/" index/prompt_opportunity.txt; cat corpus/opportunity.json; } > "$TMP"
agy --print="$(cat "$TMP")" --mode=accept-edits > "$OUT.new" 2>>"$LOG"
rm -f "$TMP"

if [ -s "$OUT.new" ] && grep -q "## 二、沒人發現的機會" "$OUT.new" && grep -q "## 四、中期看法" "$OUT.new"; then
  mv "$OUT.new" "$OUT"; log "洞察專區 ok ($(wc -c < "$OUT") bytes)"
else
  log "FAIL: 洞察專區不合規，保留 .new"; rm -f "$OUT.new"
fi

# 4.5 重建前端頁面（零 token）
python3 bin/build_site.py >> "$LOG" 2>&1 || log "WARN: build_site 失敗"

# 4.55 跨報告矛盾偵測（零 token）——參考 Karpathy LLM Wiki 的 lint 概念
if ! python3 bin/wiki_lint.py >> "$LOG" 2>&1; then
  log "WARN: 發現跨報告矛盾，需人工判斷是修正舊報告還是說明數字為何改變"
fi

# 4.6 個資閘門：公開 repo，推之前必須確認沒有雇主名稱／持倉資訊
python3 bin/check_privacy.py >> "$LOG" 2>&1 || { log "STOP: 個資檢查未通過，中止本次流程"; exit 1; }

# 5. 稽核（零 token）：數字必須回溯得到訊號表
python3 bin/validate_research.py "$DATE" >> "$LOG" 2>&1 || log "WARN: 稽核有異常，見 log"

log "=== research done (新增 $NEW) ==="
