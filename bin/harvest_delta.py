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

def load_seen():
    s = set()
    if os.path.exists(SEEN):
        with open(SEEN, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                p = line.rstrip("\n").split("\t")
                if len(p) == 2:
                    s.add((p[0], p[1]))
    # seen.tsv is only an optimization and may be absent after restoring the canonical
    # Release snapshot on another machine.  master.jsonl is the authority; without this
    # fallback a recovery host would append rediscovered rows as false daily additions.
    if os.path.exists(MASTER):
        with open(MASTER, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                repo, path = row.get("repo"), row.get("path")
                if repo and path:
                    s.add((repo, path))
    return s

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

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = os.path.join(CORPUS, f"delta-{stamp}.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    # 累積進 master，並更新 seen
    with open(MASTER, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SEEN, "a", encoding="utf-8") as fh:
        for r, p in targets:
            fh.write(f"{r}\t{p}\n")
    print(f"[delta] 新增 {len(rows)} 筆 → {out}", file=sys.stderr)
    print(out)

if __name__ == "__main__":
    main()
