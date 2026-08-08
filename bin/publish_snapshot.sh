#!/bin/bash
# Validate and publish the canonical corpus outside git history.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export TZ="Asia/Taipei"

PYTHON_BIN="${PYTHON_BIN:-python3}"
TAG="${1:-corpus-latest}"
SNAPSHOT_DATE="${SNAPSHOT_DATE:-$(date +%Y-%m-%d)}"
GZ="corpus/master.jsonl.gz"
MANIFEST="data/corpus_snapshot_manifest.json"

"$PYTHON_BIN" bin/build_corpus_snapshot.py \
  --date "$SNAPSHOT_DATE" --release-tag "$TAG" \
  --gzip-output "$GZ" --manifest "$MANIFEST"

ROWS=$("$PYTHON_BIN" -c "import json; print(json.load(open('$MANIFEST', encoding='utf-8'))['counts']['rows'])")
SEED=$("$PYTHON_BIN" -c "import json; print(json.load(open('$MANIFEST', encoding='utf-8'))['counts']['seed'])")
MODEL=$("$PYTHON_BIN" -c "import json; print(json.load(open('$MANIFEST', encoding='utf-8'))['counts']['model'])")
MASTER_SHA=$("$PYTHON_BIN" -c "import json; print(json.load(open('$MANIFEST', encoding='utf-8'))['master_sha256'])")
GZIP_SHA=$("$PYTHON_BIN" -c "import json; print(json.load(open('$MANIFEST', encoding='utf-8'))['gzip_sha256'])")
NOTES="Canonical corpus snapshot ${SNAPSHOT_DATE}.

rows=${ROWS}; seed=${SEED}; model=${MODEL}
master_sha256=${MASTER_SHA}
gzip_sha256=${GZIP_SHA}

sample=neutral is eligible for population estimates; targeted-* is topic oversampling and must not be used for population proportions."

if gh release view "$TAG" >/dev/null 2>&1; then
  gh release upload "$TAG" "$GZ" --clobber
  gh release edit "$TAG" --title "語料 rolling snapshot ${SNAPSHOT_DATE}" --notes "$NOTES"
else
  gh release create "$TAG" "$GZ" \
    --title "語料 rolling snapshot ${SNAPSHOT_DATE}" --notes "$NOTES"
fi

REMOTE_DIGEST=$(gh release view "$TAG" --json assets \
  --jq '.assets[] | select(.name=="master.jsonl.gz") | .digest')
if [ "$REMOTE_DIGEST" != "sha256:${GZIP_SHA}" ]; then
  echo "release digest mismatch: local=sha256:${GZIP_SHA} remote=${REMOTE_DIGEST}" >&2
  exit 1
fi
echo "published ${TAG}: rows=${ROWS} seed/model=${SEED}/${MODEL} digest=${REMOTE_DIGEST}"
