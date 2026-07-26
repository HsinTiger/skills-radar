#!/bin/bash
# skills-radar 每日主流程：抓取事實 → agy 產出簡報 → 更新 README → commit & push
set -uo pipefail
ROOT="$HOME/skills-radar"
cd "$ROOT" || exit 1
LOG="$ROOT/data/run.log"
DATE=$(date +%Y-%m-%d)
OUT="$ROOT/daily/$DATE.md"

log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }
log "=== run start $DATE ==="

# 1. 抓事實
FACTS=$(/usr/bin/env python3 "$ROOT/bin/fetch.py" 1 2>>"$LOG")
if [ ! -s "$FACTS" ]; then
  log "FAIL: 抓取失敗，無事實檔"
  exit 1
fi
log "facts: $FACTS ($(wc -c < "$FACTS") bytes)"

# 2. 產簡報（厚重工作外包 agy）
TMP=$(mktemp)
{ sed "s/YYYY-MM-DD/$DATE/" "$ROOT/index/prompt_daily.txt"; cat "$FACTS"; } > "$TMP"
agy --print="$(cat "$TMP")" --mode=accept-edits > "$OUT.new" 2>>"$LOG"
rm -f "$TMP"

# 3. 驗收：必須有骨架且非空，否則不覆蓋
if [ -s "$OUT.new" ] && grep -q "## 🎯 策略建議" "$OUT.new" && grep -q "### 長期" "$OUT.new"; then
  mv "$OUT.new" "$OUT"
  log "ok: $OUT ($(wc -c < "$OUT") bytes)"
else
  log "FAIL: 簡報不合規，保留 .new 供檢查"
  exit 1
fi

# 4. 零輸出偵測（吃過這個虧：排程默默產出空檔沒人發現）
SIZE=$(wc -c < "$OUT")
if [ "$SIZE" -lt 800 ]; then
  log "WARN: 簡報只有 $SIZE bytes，疑似異常"
fi

# 5. 稽核幻覺：簡報中的具體宣稱必須能回溯事實檔
if ! /usr/bin/env python3 "$ROOT/bin/audit_daily.py" "$DATE" >> "$LOG" 2>&1; then
  log "WARN: 稽核發現無法回溯的宣稱，簡報保留但需人工確認（詳見 log）"
fi

# 6. 更新 README 的最新一期連結
/usr/bin/env python3 "$ROOT/bin/build_readme.py" >> "$LOG" 2>&1

# 6.5 每日研究增量（省 token：採集/聚合/訊號全走腳本，LLM 只讀訊號表）
"$ROOT/bin/daily_research.sh" >> "$LOG" 2>&1 || log "WARN: research 步驟異常"

# 7. 推私有 repo
git add -A >> "$LOG" 2>&1
if ! git diff --cached --quiet; then
  git -c user.name="HsinBro" -c user.email="j12345453@gmail.com" \
      commit -q -m "radar: $DATE 每日情報與研究增量" >> "$LOG" 2>&1
  git push -q origin main >> "$LOG" 2>&1 && log "pushed" || log "WARN: push 失敗"
else
  log "無變動，略過 commit"
fi
log "=== run done ==="
