#!/usr/bin/env python3
"""
harvest_full.py — 大規模擴充語料。零 token。

問題：GitHub code search 每個查詢**最多只能取回 1000 筆**（10 頁 × 100），
和 total_count 顯示幾萬筆無關。所以要提高覆蓋率，唯一的辦法是切出夠多的不重疊分區。

做法：對「檔案大小」做**遞迴二分**。
  查一個區間 → 若 total_count > 900 且區間還能再切 → 對半切，各自遞迴
                → 否則就翻頁把這區間抓乾淨（最多 1000 筆）
這樣分區密度會自動貼合實際分佈：檔案多的大小區間切得細，稀疏的區間不浪費查詢。

用法: harvest_full.py [最大查詢次數] [最低區間寬度]
可以中斷後重跑，已看過的 (repo, path) 記在 seen.tsv，不會重複抓內容。
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("hc", os.path.join(ROOT, "bin", "harvest_corpus.py"))
hc = importlib.util.module_from_spec(spec); spec.loader.exec_module(hc)

CORPUS = os.path.join(ROOT, "corpus")
SEEN = os.path.join(CORPUS, "seen.tsv")
MASTER = os.path.join(CORPUS, "master.jsonl")
PART_LOG = os.path.join(CORPUS, "partitions.jsonl")

MAX_QUERIES = int(sys.argv[1]) if len(sys.argv) > 1 else 700
MIN_WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 8
PER_REPO_CAP = 8

queries_used = 0

def count(qrange):
    global queries_used
    d = hc.gh(f"search/code?q=filename:SKILL.md+size:{qrange}&per_page=1")
    queries_used += 1
    time.sleep(2.1)
    return d.get("total_count", 0) if isinstance(d, dict) else 0

def drain(qrange, found):
    """把一個區間翻頁抓乾淨"""
    global queries_used
    for page in range(1, 11):
        d = hc.gh(f"search/code?q=filename:SKILL.md+size:{qrange}&per_page=100&page={page}")
        queries_used += 1
        time.sleep(2.1)
        items = d.get("items") or [] if isinstance(d, dict) else []
        if not items:
            break
        for it in items:
            repo = (it.get("repository") or {}).get("full_name")
            path = it.get("path")
            if not repo or not path:
                continue
            found.setdefault(repo, set())
            if len(found[repo]) < PER_REPO_CAP:
                found[repo].add(path)
        if len(items) < 100:
            break

def partition(lo, hi, found, depth=0):
    """遞迴二分：切到每個區間的 total_count 落在可完整取回的範圍"""
    if queries_used >= MAX_QUERIES:
        return
    qrange = f"{lo}..{hi}" if hi < 10**9 else f">{lo}"
    n = count(qrange)
    if n == 0:
        return
    if n <= 900 or (hi - lo) <= MIN_WIDTH or depth > 14:
        drain(qrange, found)
        with open(PART_LOG, "a") as fh:
            fh.write(json.dumps({"range": qrange, "reported": n, "depth": depth}) + "\n")
        return
    mid = (lo + hi) // 2
    partition(lo, mid, found, depth + 1)
    partition(mid + 1, hi, found, depth + 1)

def load_seen():
    s = set()
    if os.path.exists(SEEN):
        for line in open(SEEN, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2:
                s.add((p[0], p[1]))
    return s

def main():
    seen = load_seen()
    print(f"[full] 起始已知 {len(seen)} 筆", file=sys.stderr)
    found = {}
    # 0..40000 涵蓋絕大多數 SKILL.md；超過的另外掃一次
    partition(0, 40000, found)
    if queries_used < MAX_QUERIES:
        drain(">40000", found)

    targets = [(r, p) for r, ps in found.items() for p in ps if (r, p) not in seen]
    print(f"[full] 用了 {queries_used} 次查詢，掃到 {sum(len(v) for v in found.values())} 筆，"
          f"新的 {len(targets)} 筆", file=sys.stderr)
    if not targets:
        return

    repos = sorted({r for r, _ in targets})
    meta = {}
    def rmeta(r):
        d = hc.gh(f"repos/{r}")
        if isinstance(d, dict) and "_error" not in d:
            meta[r] = {"stars": d.get("stargazers_count"), "created": d.get("created_at"),
                       "topics": d.get("topics") or [],
                       "owner_type": (d.get("owner") or {}).get("type")}
    print(f"[full] 補 {len(repos)} 個 repo metadata...", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(rmeta, repos))

    done = [0]
    rows = []
    def work(t):
        repo, path = t
        txt = hc.fetch_raw(repo, path)
        done[0] += 1
        if done[0] % 500 == 0:
            print(f"    內容 {done[0]}/{len(targets)}", file=sys.stderr)
        if not txt or len(txt) < 40:
            return None
        p = hc.parse_skill(txt)
        m = meta.get(repo, {})
        return {"repo": repo, "path": path, "stars": m.get("stars"),
                "repo_created": m.get("created"), "repo_topics": m.get("topics"),
                "owner_type": m.get("owner_type"), "chars": len(txt),
                "first_seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"), **p}
    with ThreadPoolExecutor(max_workers=14) as ex:
        for r in ex.map(work, targets):
            if r and (r["name"] or r["description"]):
                rows.append(r)

    with open(MASTER, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SEEN, "a", encoding="utf-8") as fh:
        for r, p in targets:
            fh.write(f"{r}\t{p}\n")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    print(f"[full] 新增 {len(rows)} 筆，master 累計增長", file=sys.stderr)
    print(os.path.join(CORPUS, f"full-{stamp}.jsonl"))

if __name__ == "__main__":
    main()
