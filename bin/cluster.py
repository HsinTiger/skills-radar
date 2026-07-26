#!/usr/bin/env python3
"""
cluster.py — 無監督分群，用來發現「既有分類法沒涵蓋的新用法」。零 token。

為什麼需要這個：
監督式分類器只能把東西塞進我預設的 18 個領域。真正的新東西——某個還沒有名字的用法——
會被硬塞進 other 或最像的類別，然後消失。分群不預設類別，讓結構自己浮現。

輸出 corpus/clusters.json：每群的代表詞、樣本、以及它在既有分類裡的分佈。
**若某群成員在既有領域裡散落多處、或大量落在 other，那就是分類法沒涵蓋的新用法**，
也是最值得人看的東西。這份輸出可再餵給 LLM 命名（唯一的 LLM 成本）。
"""
import json, os, sys
import numpy as np
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")
K = int(sys.argv[1]) if len(sys.argv) > 1 else 120

rows = []
for line in open(MASTER, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except Exception:
        pass

def text_of(r):
    return " ".join([(r.get("name") or ""), (r.get("description") or ""),
                     (r.get("body_head") or "")[:600],
                     " ".join(r.get("repo_topics") or [])])

X_text = [text_of(r) for r in rows]
vec = TfidfVectorizer(sublinear_tf=True, min_df=3, max_df=0.5, max_features=80000,
                      ngram_range=(1, 2), strip_accents="unicode")
X = vec.fit_transform(X_text)
print(f"向量化：{X.shape[0]} 筆 × {X.shape[1]} 維")

km = MiniBatchKMeans(n_clusters=K, random_state=0, n_init=5, batch_size=2048)
lab = km.fit_predict(X)
terms = np.array(vec.get_feature_names_out())
order = km.cluster_centers_.argsort()[:, ::-1]

out = []
for c in range(K):
    idx = np.where(lab == c)[0]
    if len(idx) == 0:
        continue
    doms = Counter(rows[i].get("domain") or "unlabeled" for i in idx)
    tasks = Counter(rows[i].get("task") or "unlabeled" for i in idx)
    # 分散度：最大領域佔比越低，表示這群橫跨多個既有領域＝分類法沒抓到它
    top_dom, top_n = doms.most_common(1)[0]
    dispersion = round(1 - top_n / len(idx), 2)
    other_pct = round(100 * doms.get("other", 0) / len(idx), 1)
    reps = sorted(idx, key=lambda i: -(rows[i].get("stars") or 0))[:5]
    out.append({
        "cluster": c, "n": int(len(idx)),
        "top_terms": [terms[j] for j in order[c, :12]],
        "domain_mix": dict(doms.most_common(5)),
        "task_mix": dict(tasks.most_common(4)),
        "dispersion": dispersion,          # 越高＝越可能是新類別
        "other_pct": other_pct,
        "samples": [{"name": rows[i].get("name", "")[:80],
                     "pain": rows[i].get("pain"),
                     "stars": rows[i].get("stars"),
                     "repo": rows[i].get("repo")} for i in reps],
    })

out.sort(key=lambda c: -c["n"])
json.dump({"k": K, "n": len(rows), "clusters": out},
          open(os.path.join(ROOT, "corpus", "clusters.json"), "w"),
          ensure_ascii=False, indent=1)

print(f"\n分群完成 k={K}。最可能是「新類別」的前 10 群（跨領域分散度高）：")
for c in sorted(out, key=lambda c: (-c["dispersion"], -c["n"]))[:10]:
    print(f"  #{c['cluster']:3d} n={c['n']:4d} 分散度={c['dispersion']:.2f} "
          f"other={c['other_pct']:4.1f}%  {' / '.join(c['top_terms'][:6])}")
print(f"\n→ corpus/clusters.json")
