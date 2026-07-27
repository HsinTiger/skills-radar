#!/bin/bash
# 把語料快照上傳到 GitHub Release，避免塞進 git 歷史。
# 原始 master.jsonl 約 75MB 且每日成長；壓縮後約 20MB。
# git 每天存一份 20MB 的二進位檔，一個月就是 600MB 歷史——所以走 Release 而非版控。
set -uo pipefail
ROOT="$HOME/skills-radar"
cd "$ROOT" || exit 1
TAG="corpus-$(date +%Y%m%d)"
GZ="corpus/master.jsonl.gz"

gzip -9 -c corpus/master.jsonl > "$GZ" || exit 1
SIZE=$(ls -lh "$GZ" | awk '{print $5}')
N=$(wc -l < corpus/master.jsonl | tr -d ' ')

gh release create "$TAG" "$GZ" \
  --title "語料快照 $(date +%Y-%m-%d)" \
  --notes "樣本 ${N} 筆，壓縮後 ${SIZE}。

解壓後為 JSON Lines，每行一筆 skill 的 metadata 與分類標籤。
\`sample\` 欄位標示抽樣方式：neutral（中立分層抽樣，可用於估計比例）／
targeted-*（主題過取樣，**不可**用於估計比例，僅供該主題內部結構分析）。" \
  2>/dev/null || gh release upload "$TAG" "$GZ" --clobber
echo "已發佈 $TAG（${N} 筆 / ${SIZE}）"
