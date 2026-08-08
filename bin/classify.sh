#!/bin/bash
# 把語料切成批次，派給 agy 分類（厚重機械工作外包）
# 用法: classify.sh <corpus.jsonl> [每批筆數] [並行數]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
CORPUS="$1"
BATCH=${2:-40}
PAR=${3:-4}
MODE=${4:-fresh}
MAX_BUDGET_USD=${CLASSIFY_MAX_BUDGET_USD:-0.60}
WORK="$ROOT/corpus/.batches"
OUTD="$ROOT/corpus/.classified"
LOG="$ROOT/corpus/classify.log"
mkdir -p "$WORK" "$OUTD"
rm -f "$WORK"/*.jsonl
if [ "$MODE" != "resume" ]; then
  rm -f "$OUTD"/*.jsonl "$OUTD"/*.raw
  : > "$LOG"
else
  echo "[resume] 保留已完成 batch" >> "$LOG"
fi

# 切批次：只餵分類需要的欄位，減少 token 與注入面
if ! python3 - "$CORPUS" "$WORK" "$BATCH" <<'PY'
import json, sys, os
corpus, work, batch = sys.argv[1], sys.argv[2], int(sys.argv[3])
with open(corpus, encoding="utf-8") as handle:
    rows = [json.loads(l) for l in handle if l.strip()]
for b in range(0, len(rows), batch):
    chunk = rows[b:b+batch]
    with open(os.path.join(work, f"b{b//batch:04d}.jsonl"), "w") as fh:
        for i, r in enumerate(chunk, start=b):
            fh.write(json.dumps({
                "i": i,
                "name": r.get("name", "")[:120],
                "description": r.get("description", "")[:400],
                "body_head": r.get("body_head", "")[:450],
                "repo_topics": (r.get("repo_topics") or [])[:6],
            }, ensure_ascii=False) + "\n")
print(f"{len(rows)} 筆 → {(len(rows)+batch-1)//batch} 批")
PY
then
  echo "分類失敗：無法以 UTF-8 切分輸入" | tee -a "$LOG" >&2
  exit 1
fi

if ! compgen -G "$WORK/*.jsonl" >/dev/null; then
  echo "分類失敗：未產生任何 batch" | tee -a "$LOG" >&2
  exit 1
fi

one() {
  set -o pipefail
  f="$1"; base=$(basename "$f" .jsonl)
  expected=$(grep -cve '^[[:space:]]*$' "$f")
  if [ -f "$OUTD/$base.jsonl" ]; then
    existing=$(grep -cve '^[[:space:]]*$' "$OUTD/$base.jsonl")
    if [ "$existing" -eq "$expected" ]; then
      echo "[skip] $base 已完成 $existing 筆" >> "$LOG"
      return 0
    fi
  fi
  tmp=$(mktemp)
  raw="$OUTD/$base.raw"
  { cat "$ROOT/index/prompt_classify.txt"; cat "$f"; } > "$tmp"
  if command -v agy >/dev/null 2>&1; then
    if ! agy --print="$(cat "$tmp")" --mode=accept-edits > "$raw" 2>>"$LOG"; then
      echo "[FAIL] $base provider 失敗" >> "$LOG"
      rm -f "$tmp" "$OUTD/$base.jsonl"
      return 1
    fi
  elif command -v claude >/dev/null 2>&1; then
    if ! claude --print --bare --tools "" --model claude-sonnet-5 --effort low \
      --max-budget-usd "$MAX_BUDGET_USD" --no-session-persistence --permission-mode dontAsk \
      < "$tmp" > "$raw" 2>>"$LOG"; then
      echo "[FAIL] $base provider 失敗" >> "$LOG"
      rm -f "$tmp" "$OUTD/$base.jsonl"
      return 1
    fi
  else
    echo "[FAIL] $base 找不到 agy 或 claude" >> "$LOG"
    rm -f "$tmp"
    return 1
  fi
  rm -f "$tmp"
  if ! python3 "$ROOT/bin/extract_classification.py" "$raw" "$OUTD/$base.jsonl" 2>>"$LOG"; then
    echo "[FAIL] $base 無可解析 JSON 輸出；raw 已保留" >> "$LOG"
    rm -f "$OUTD/$base.jsonl"
    return 1
  fi
  n=$(grep -cve '^[[:space:]]*$' "$OUTD/$base.jsonl")
  if [ "$n" -ne "$expected" ]; then
    echo "[FAIL] $base 需要 $expected 筆，只有 $n 筆；raw 已保留" >> "$LOG"
    rm -f "$OUTD/$base.jsonl"
    return 1
  fi
  echo "[ok  ] $base $n 筆" >> "$LOG"
}
export ROOT OUTD LOG
export -f one

if ! find "$WORK" -maxdepth 1 -name '*.jsonl' -print0 \
  | xargs -0 -P "$PAR" -I{} bash -c 'one "$@"' _ {}; then
  echo "分類失敗：至少一個 batch 未完成" | tee -a "$LOG" >&2
  exit 1
fi
if ! compgen -G "$OUTD/*.jsonl" >/dev/null; then
  echo "分類失敗：provider 沒有有效輸出" | tee -a "$LOG" >&2
  exit 1
fi
cat "$OUTD"/*.jsonl > "$ROOT/corpus/classified.jsonl"
EXPECTED=$(grep -cve '^[[:space:]]*$' "$CORPUS")
ACTUAL=$(grep -cve '^[[:space:]]*$' "$ROOT/corpus/classified.jsonl")
if [ "$ACTUAL" -ne "$EXPECTED" ]; then
  echo "分類失敗：輸入 $EXPECTED 筆，完整輸出只有 $ACTUAL 筆" | tee -a "$LOG" >&2
  exit 1
fi
echo "分類完成：$ACTUAL 筆" | tee -a "$LOG"
