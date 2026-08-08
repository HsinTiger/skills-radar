#!/bin/bash
# skills-radar 每日主流程：抓取事實 → AI 產出 → 研究/摘要 → 更新 README → publish
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
LOG="$ROOT/data/run.log"
export TZ="Asia/Taipei"
export SKILLS_RADAR_RUN_CONTEXT="${SKILLS_RADAR_RUN_CONTEXT:-manual}"
DATE=$(date +%Y-%m-%d)
OUT="$ROOT/daily/$DATE.md"
LOCK_DIR="$ROOT/data/run_daily.lock"

log() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }

release_lock() {
  rm -f "$LOCK_DIR/pid"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  LOCK_PID=$(cat "$LOCK_DIR/pid" 2>/dev/null || true)
  if [[ "$LOCK_PID" =~ ^[0-9]+$ ]] && kill -0 "$LOCK_PID" 2>/dev/null; then
    log "STOP: run_daily already active pid=$LOCK_PID"
    exit 75
  fi
  # Do not steal a newly-created lock during the tiny mkdir -> pid write window.
  # A dead lock is recoverable after six hours, well before the next daily run.
  LOCK_MTIME=$(stat -f %m "$LOCK_DIR" 2>/dev/null || stat -c %Y "$LOCK_DIR" 2>/dev/null || echo 0)
  NOW_EPOCH=$(date +%s)
  if ! [[ "$LOCK_MTIME" =~ ^[0-9]+$ ]] || [ $((NOW_EPOCH - LOCK_MTIME)) -lt 21600 ]; then
    log "STOP: lock owner is not provably stale: $LOCK_DIR"
    exit 75
  fi
  rm -f "$LOCK_DIR/pid"
  if ! rmdir "$LOCK_DIR" 2>/dev/null || ! mkdir "$LOCK_DIR" 2>/dev/null; then
    log "STOP: stale lock could not be recovered: $LOCK_DIR"
    exit 75
  fi
fi
echo "$$" > "$LOCK_DIR/pid"
trap release_lock EXIT HUP INT TERM

log "=== run start $DATE ==="

# 0. 排程機器先以 fast-forward 對齊 remote；分歧或 dirty conflict 必須明確失敗。
if ! git pull --ff-only origin main >> "$LOG" 2>&1; then
  log "STOP: git pull --ff-only 失敗，未開始產生今日資料"
  exit 1
fi

# 1. 抓事實
FACTS=$(/usr/bin/env python3 "$ROOT/bin/fetch.py" 1 2>>"$LOG")
if [ ! -s "$FACTS" ]; then
  log "FAIL: 抓取失敗，無事實檔"
  exit 1
fi
log "facts: $FACTS ($(wc -c < "$FACTS") bytes)"

# 2-3. 產簡報並驗收。Mac 優先 agy；無 agy 時使用無工具 Claude CLI。
if ! /usr/bin/env python3 "$ROOT/bin/generate_ai_artifact.py" daily \
    --date "$DATE" --input "$FACTS" --output "$OUT" >> "$LOG" 2>&1; then
  log "FAIL: 每日簡報 AI provider 或結構驗收失敗"
  exit 1
fi
log "ok: $OUT ($(wc -c < "$OUT") bytes)"

# 4. 零輸出偵測（吃過這個虧：排程默默產出空檔沒人發現）
SIZE=$(wc -c < "$OUT")
if [ "$SIZE" -lt 800 ]; then
  log "WARN: 簡報只有 $SIZE bytes，疑似異常"
fi

# 5. 稽核幻覺：簡報中的具體宣稱必須能回溯事實檔
if ! /usr/bin/env python3 "$ROOT/bin/audit_daily.py" "$DATE" >> "$LOG" 2>&1; then
  log "WARN: 稽核發現無法回溯的宣稱，簡報保留但需人工確認（詳見 log）"
fi

# 6. 每日研究增量（省 token：採集/聚合/訊號全走腳本，LLM 只讀訊號表）
if ! "$ROOT/bin/daily_research.sh" >> "$LOG" 2>&1; then
  log "FAIL: research 步驟異常，停止 commit/push，避免發佈部分更新"
  exit 1
fi

# 6.5 研究建議已產生後才重建 README，避免自動 run 永遠連到前一天。
/usr/bin/env python3 "$ROOT/bin/build_readme.py" >> "$LOG" 2>&1 || {
  log "STOP: README 重建失敗"; exit 1;
}

# 6.8 每次成功 run 更新 rolling Release；否則 tracked model report 會再次
# 與可下載 master 漂移。週一另外保留 immutable dated archive。
"$ROOT/bin/publish_snapshot.sh" corpus-latest >> "$LOG" 2>&1 || {
  log "STOP: canonical rolling snapshot 發佈或 digest readback 失敗"; exit 1;
}
if [ "$(date +%u)" = "1" ]; then
  "$ROOT/bin/publish_snapshot.sh" "corpus-$(date +%Y%m%d)" >> "$LOG" 2>&1 \
    || log "WARN: weekly dated archive 發佈失敗；rolling snapshot 已成功"
fi

# 7. 推 repo
git add -A >> "$LOG" 2>&1
if ! git diff --cached --quiet; then
  git -c user.name="HsinBro" -c user.email="j12345453@gmail.com" \
      commit -q -m "radar: $DATE 每日情報與研究增量" >> "$LOG" 2>&1
  if git push -q origin main >> "$LOG" 2>&1; then
    log "pushed"
  else
    log "FAIL: push 失敗；launchd 必須收到非零狀態，watchdog 會保持紅燈"
    exit 1
  fi
else
  log "無變動，略過 commit"
fi
log "=== run done ==="
