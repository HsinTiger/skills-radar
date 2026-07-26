#!/usr/bin/env python3
"""
把分類結果聚合成統計事實，供最後的洞察報告使用。
只算數字，不下判斷 —— 判斷留給報告階段，且必須基於這裡算出來的數字。
"""
import json, os, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
corpus_p = sys.argv[1] if len(sys.argv) > 1 else None
cls_p = os.path.join(ROOT, "corpus", "classified.jsonl")

corpus = {}
if corpus_p and os.path.exists(corpus_p):
    for i, line in enumerate(open(corpus_p, encoding="utf-8", errors="replace")):
        corpus[i] = json.loads(line)

rows = []
seen = set()
for line in open(cls_p, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        r = json.loads(line)
    except Exception:
        continue
    i = r.get("i")
    if i in seen:
        continue
    seen.add(i)
    src = corpus.get(i, {})
    r["stars"] = src.get("stars") or 0
    r["repo"] = src.get("repo")
    r["repo_created"] = (src.get("repo_created") or "")[:7]
    r["chars"] = src.get("chars") or 0
    rows.append(r)

def cnt(field):
    return Counter(r.get(field) or "unknown" for r in rows)

def pct(c, total):
    return {k: {"n": v, "pct": round(100 * v / total, 1)} for k, v in c.most_common()}

N = len(rows)
out = {
    "n_classified": N,
    "domain": pct(cnt("domain"), N),
    "task": pct(cnt("task"), N),
    "target": pct(cnt("target"), N),
    "maturity": pct(cnt("maturity"), N),
    "profession_top": dict(cnt("profession").most_common(30)),
    "injection_suspect": sum(1 for r in rows if r.get("injection_suspect")),
}

# 交叉表：領域 × 任務型態 —— 看不同行業把 AI 用在哪一層
cross = defaultdict(Counter)
for r in rows:
    cross[r.get("domain") or "unknown"][r.get("task") or "unknown"] += 1
out["domain_x_task"] = {d: dict(c.most_common()) for d, c in
                        sorted(cross.items(), key=lambda kv: -sum(kv[1].values()))}

# 領域 × 成熟度 —— 哪些領域只是玩玩，哪些真的上線
cross2 = defaultdict(Counter)
for r in rows:
    cross2[r.get("domain") or "unknown"][r.get("maturity") or "unknown"] += 1
out["domain_x_maturity"] = {d: dict(c) for d, c in
                            sorted(cross2.items(), key=lambda kv: -sum(kv[1].values()))}

# 時間軸：repo 建立月份 × 領域 —— 看哪些領域是新進場的
tl = defaultdict(Counter)
for r in rows:
    if r.get("repo_created"):
        tl[r["repo_created"]][r.get("domain") or "unknown"] += 1
out["timeline_by_month"] = {m: dict(c.most_common(6)) for m, c in sorted(tl.items())[-15:]}

# 各領域的痛點樣本（給報告當質性素材）
pains = defaultdict(list)
for r in sorted(rows, key=lambda r: -(r.get("stars") or 0)):
    d = r.get("domain") or "unknown"
    p = (r.get("pain") or "").strip()
    if p and len(pains[d]) < 12:
        pains[d].append({"pain": p, "stars": r["stars"], "repo": r["repo"],
                         "profession": r.get("profession")})
out["pain_samples"] = dict(pains)

# 高星樣本：社群實際認可的是哪些
out["top_by_stars"] = [
    {k: r.get(k) for k in ("repo", "domain", "profession", "task", "maturity", "pain", "stars")}
    for r in sorted(rows, key=lambda r: -(r.get("stars") or 0))[:40]]

json.dump(out, open(os.path.join(ROOT, "corpus", "aggregate.json"), "w"),
          ensure_ascii=False, indent=1)
print(f"聚合完成：{N} 筆")
for k in ("domain", "task", "maturity"):
    print(f"\n{k}:")
    for kk, vv in list(out[k].items())[:8]:
        print(f"   {kk:24s} {vv['n']:5d}  {vv['pct']:5.1f}%")
