#!/usr/bin/env python3
"""
harvest_delta.py — 每日增量採集。零 token。

省成本的關鍵：搜尋（API 呼叫）很便宜，內容抓取與分類才貴。
所以每天照樣全量掃一次 code search 找出「有哪些 SKILL.md 存在」，
但只對**沒看過的**路徑抓內容、只把新的送去分類。
穩定狀態下每天新增大約幾十到幾百筆，而不是 5,600 筆。
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("hc", os.path.join(ROOT, "bin", "harvest_corpus.py"))
hc = importlib.util.module_from_spec(spec); spec.loader.exec_module(hc)

CORPUS = os.path.join(ROOT, "corpus")
SEEN = os.path.join(CORPUS, "seen.tsv")
MASTER = os.path.join(CORPUS, "master.jsonl")

def _row_key(row, source):
    key = (row.get("repo"), row.get("path"))
    if not all(isinstance(value, str) and value for value in key):
        raise ValueError(f"{source} contains a row without repo/path")
    return key


def _read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} contains invalid JSON") from exc
    return rows


def load_seen():
    """Return canonical corpus keys; seen.tsv is only a bootstrap cache.

    A restored or stale seen.tsv must never hide a path that is absent from the
    append-only master.  When master exists it is therefore the sole authority.
    """
    if os.path.exists(MASTER):
        return {_row_key(row, MASTER) for row in _read_jsonl(MASTER)}

    seen = set()
    if os.path.exists(SEEN):
        with open(SEEN, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 2 and all(parts):
                    seen.add((parts[0], parts[1]))
    return seen


def merge_daily_delta(path, rows):
    """Atomically merge new rows into the date-level delta without shrinking it."""
    combined = _read_jsonl(path)
    positions = {}
    for index, row in enumerate(combined):
        key = _row_key(row, path)
        if key in positions:
            raise ValueError(f"{path} contains duplicate repo/path {key!r}")
        positions[key] = index
    for row in rows:
        key = _row_key(row, "collector batch")
        if key not in positions:
            positions[key] = len(combined)
            combined.append(row)

    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            for row in combined:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return len(combined)

def main():
    seen = load_seen()
    print(f"[delta] 已知 {len(seen)} 筆", file=sys.stderr)

    found = hc.search_skill_files()
    targets = [(r, p) for r, ps in found.items() for p in ps if (r, p) not in seen]
    print(f"[delta] 掃到 {sum(len(v) for v in found.values())} 筆，其中新的 {len(targets)} 筆", file=sys.stderr)

    if not targets:
        print("", end="")
        return

    repos = sorted({r for r, _ in targets})
    meta = {}
    def rmeta(r):
        d = hc.gh(f"repos/{r}")
        if "_error" not in d:
            meta[r] = {"stars": d.get("stargazers_count"), "created": d.get("created_at"),
                       "topics": d.get("topics") or [], "owner_type": (d.get("owner") or {}).get("Type") or (d.get("owner") or {}).get("type")}
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(rmeta, repos))

    rows = []
    def work(t):
        repo, path = t
        txt = hc.fetch_raw(repo, path)
        if not txt or len(txt) < 40:
            return None
        p = hc.parse_skill(txt)
        m = meta.get(repo, {})
        return {"repo": repo, "path": path, "stars": m.get("stars"),
                "repo_created": m.get("created"), "repo_topics": m.get("topics"),
                "owner_type": m.get("owner_type"), "chars": len(txt),
                "first_seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"), **p}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for r in ex.map(work, targets):
            if r and (r["name"] or r["description"]):
                rows.append(r)

    if not rows:
        print("[delta] 沒有可用的新內容；保留既有當日 delta", file=sys.stderr)
        return

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = os.path.join(CORPUS, f"delta-{stamp}.jsonl")
    daily_total = merge_daily_delta(out, rows)
    # 累積進 master，並更新 seen
    with open(MASTER, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SEEN, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(f"{row['repo']}\t{row['path']}\n")
    print(f"[delta] 本次新增 {len(rows)} 筆；當日累積 {daily_total} 筆 → {out}", file=sys.stderr)
    print(out)

if __name__ == "__main__":
    main()
