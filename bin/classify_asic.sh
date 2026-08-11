#!/bin/bash
# Strict LLM labelling for ASIC secondary axes. Run only on a bounded sample.
# Usage: classify_asic.sh corpus/asic-golden-sample.jsonl [batch-size] [parallelism]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
CORPUS="$1"
BATCH=${2:-30}
PAR=${3:-2}
WORK="$ROOT/corpus/.asic-batches"
OUTD="$ROOT/corpus/.asic-classified"
LOG="$ROOT/corpus/asic-classify.log"
mkdir -p "$WORK" "$OUTD"
rm -f "$WORK"/*.jsonl "$OUTD"/*.jsonl
: > "$LOG"

python3 "$ROOT/bin/security_gate.py" verify "$CORPUS" >> "$LOG" 2>&1 || {
  echo "ASIC classification blocked: input failed security gate" >&2
  exit 1
}
if ! command -v claude >/dev/null 2>&1; then
  echo "ASIC classification blocked: tool-less claude provider is unavailable" >&2
  exit 1
fi

python3 - "$CORPUS" "$WORK" "$BATCH" <<'PY'
import json, sys, os
corpus, work, batch = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [json.loads(line) for line in open(corpus) if line.strip()]
for start in range(0, len(rows), batch):
    with open(os.path.join(work, f"b{start // batch:04d}.jsonl"), "w") as fh:
        for i, row in enumerate(rows[start:start + batch], start=start):
            fh.write(json.dumps({
                "i": i,
                "name": (row.get("name") or "")[:120],
                "description": (row.get("description") or "")[:500],
                "body_head": (row.get("body_head") or "")[:1000],
                "path": (row.get("path") or "")[:300],
                "repo_topics": (row.get("repo_topics") or [])[:6],
            }, ensure_ascii=False) + "\n")
print(f"{len(rows)} rows -> {(len(rows) + batch - 1) // batch} batches")
PY

one() {
  f="$1"
  base=$(basename "$f" .jsonl)
  tmp=$(mktemp)
  { cat "$ROOT/index/prompt_asic_classify.txt"; cat "$f"; } > "$tmp"
  claude --print --bare --tools "" --model claude-sonnet-5 --effort low \
    --max-budget-usd "${CLASSIFY_ASIC_MAX_BUDGET_USD:-0.60}" \
    --no-session-persistence --permission-mode dontAsk \
    < "$tmp" 2>>"$ROOT/corpus/asic-classify.log" \
    | grep -E '^[[:space:]]*\{' | sed 's/^[[:space:]]*//' \
    > "$ROOT/corpus/.asic-classified/$base.jsonl"
  rm -f "$tmp"
}
export -f one

find "$WORK" -maxdepth 1 -name '*.jsonl' -print0 \
  | xargs -0 -P "$PAR" -I{} bash -c 'one "$@"' _ {}
cat "$OUTD"/*.jsonl > "$ROOT/corpus/asic_classified.jsonl"
python3 "$ROOT/bin/merge_asic_classified.py" \
  "$CORPUS" "$ROOT/corpus/asic_classified.jsonl"
