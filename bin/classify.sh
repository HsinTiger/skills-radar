#!/bin/bash
# 把語料切成批次，派給 agy 分類（厚重機械工作外包）
# 用法: classify.sh <corpus.jsonl> [每批筆數] [並行數]
set -uo pipefail
ROOT="$HOME/skills-radar"
CORPUS="$1"
BATCH=${2:-40}
PAR=${3:-4}
WORK="$ROOT/corpus/.batches"
OUTD="$ROOT/corpus/.classified"
LOG="$ROOT/corpus/classify.log"
mkdir -p "$WORK" "$OUTD"
rm -f "$WORK"/*.jsonl "$OUTD"/*.jsonl
: > "$LOG"

# 切批次：只餵分類需要的欄位，減少 token 與注入面
python3 - "$CORPUS" "$WORK" "$BATCH" <<'PY'
import json, sys, os
corpus, work, batch = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [json.loads(l) for l in open(corpus)]
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

one() {
  f="$1"; base=$(basename "$f" .jsonl)
  OUTD="$HOME/skills-radar/corpus/.classified"; LOG="$HOME/skills-radar/corpus/classify.log"
  tmp=$(mktemp)
  { cat "$HOME/skills-radar/index/prompt_classify.txt"; cat "$f"; } > "$tmp"
  agy --print="$(cat "$tmp")" --mode=accept-edits 2>>"$LOG" \
    | grep -E '^[[:space:]]*{' | sed 's/^[[:space:]]*//' > "$OUTD/$base.jsonl"
  rm -f "$tmp"
  n=$(wc -l < "$OUTD/$base.jsonl" | tr -d ' ')
  if [ "$n" -lt 1 ]; then
    echo "[FAIL] $base 無有效輸出" >> "$LOG"; rm -f "$OUTD/$base.jsonl"
  else
    echo "[ok  ] $base $n 筆" >> "$LOG"
  fi
}
export -f one

ls "$WORK"/*.jsonl | xargs -P "$PAR" -I{} bash -c 'one "$@"' _ {}
cat "$OUTD"/*.jsonl 2>/dev/null > "$ROOT/corpus/classified.jsonl"
echo "分類完成：$(wc -l < "$ROOT/corpus/classified.jsonl") 筆" | tee -a "$LOG"
