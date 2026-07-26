#!/usr/bin/env python3
"""把新分類結果併回 master.jsonl（依 repo+path 對位）。零 token。
順便驗證標籤合法性——agy 可能吐出不在列舉內的值，這裡直接擋掉。"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
delta_p = sys.argv[1]
cls_p = os.path.join(ROOT, "corpus", "classified.jsonl")

DOMAINS = {"software-dev","data-analytics","devops-infra","security","hardware-eda",
 "research-academia","writing-content","marketing-growth","design-creative","finance-investing",
 "legal-compliance","healthcare-bio","education-training","sales-crm","ops-admin",
 "personal-productivity","ai-agent-tooling","other"}
TASKS = {"generate","transform","analyze","verify","orchestrate","retrieve","configure"}
TARGETS = {"self","team","client","public","agent"}
MATS = {"toy","workflow","production"}

delta = [json.loads(l) for l in open(delta_p, encoding="utf-8", errors="replace") if l.strip()]
cls = {}
for l in open(cls_p, encoding="utf-8", errors="replace"):
    l = l.strip()
    if not l: continue
    try:
        r = json.loads(l)
        if r.get("i") is not None: cls[r["i"]] = r
    except Exception: pass

bad = 0
merged = []
for i, d in enumerate(delta):
    c = cls.get(i)
    if not c: continue
    if c.get("domain") not in DOMAINS or c.get("task") not in TASKS \
       or c.get("target") not in TARGETS or c.get("maturity") not in MATS:
        bad += 1
        continue
    for k in ("domain","profession","task","target","maturity","pain","injection_suspect"):
        d[k] = c.get(k)
    merged.append(d)

master_p = os.path.join(ROOT, "corpus", "master.jsonl")
lines = [json.loads(l) for l in open(master_p, encoding="utf-8", errors="replace") if l.strip()]
idx = {(r["repo"], r["path"]): n for n, r in enumerate(lines)}
for d in merged:
    k = (d["repo"], d["path"])
    if k in idx: lines[idx[k]] = d
    else: lines.append(d)
with open(master_p, "w", encoding="utf-8") as fh:
    for r in lines: fh.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"[merge] 併入 {len(merged)} 筆，標籤不合法剔除 {bad} 筆，master 共 {len(lines)} 筆")
