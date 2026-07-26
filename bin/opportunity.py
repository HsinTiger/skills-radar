#!/usr/bin/env python3
"""
opportunity.py — 用純計算找出「機會訊號」。零 token。

設計理念：機會的判斷必須先有可驗證的量化訊號，LLM 只負責解讀，不負責發明。
把能算的全部算完，LLM 的輸入就從 5,000 筆原始資料縮成一張幾 KB 的訊號表 —— 這是省 token 的主要來源。

兩類訊號：
A. 已取得成績（traction）：真的上線、有人用、規模夠。
B. 反向機會（gap）：大家還沒補上的洞。用「應該有多少 vs 實際有多少」的落差來定義，
   而不是憑感覺說哪裡有機會。
"""
import json, os, sys
from collections import Counter, defaultdict
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")

rows = []
for line in open(MASTER, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        r = json.loads(line)
    except Exception:
        continue
    if r.get("domain"):
        rows.append(r)

N = len(rows)
TASKS = ["generate", "transform", "analyze", "verify", "orchestrate", "retrieve", "configure"]
global_task = Counter(r.get("task") for r in rows)
global_task_pct = {t: global_task.get(t, 0) / N for t in TASKS}
global_prod = sum(1 for r in rows if r.get("maturity") == "production") / N

by_dom = defaultdict(list)
for r in rows:
    by_dom[r["domain"]].append(r)

# ---------- A. 已取得成績 ----------
traction = []
for d, rs in by_dom.items():
    n = len(rs)
    if n < 30:
        continue
    prod = sum(1 for r in rs if r.get("maturity") == "production") / n
    stars = [r.get("stars") or 0 for r in rs]
    agent_facing = sum(1 for r in rs if r.get("target") == "agent") / n
    traction.append({
        "domain": d, "n": n,
        "production_pct": round(100 * prod, 1),
        "vs_global_production": round(100 * (prod - global_prod), 1),
        "median_stars": int(median(stars)),
        "p90_stars": int(sorted(stars)[int(0.9 * (n - 1))]),
        "agent_facing_pct": round(100 * agent_facing, 1),
    })
traction.sort(key=lambda x: -x["vs_global_production"])

# ---------- B1. 能力缺口：某領域缺哪一種任務型態 ----------
task_gaps = []
for d, rs in by_dom.items():
    n = len(rs)
    if n < 50:
        continue
    c = Counter(r.get("task") for r in rs)
    for t in TASKS:
        expected = global_task_pct[t] * n
        observed = c.get(t, 0)
        if expected >= 5:
            deficit = expected - observed
            ratio = observed / expected if expected else 0
            if ratio < 0.55:      # 明顯低於全體水準
                task_gaps.append({
                    "domain": d, "task": t, "domain_n": n,
                    "observed": observed, "expected": round(expected, 1),
                    "ratio_vs_global": round(ratio, 2),
                })
task_gaps.sort(key=lambda x: (x["ratio_vs_global"], -x["domain_n"]))

# ---------- B2. 做了一半：workflow 多但 production 少 ----------
unfinished = []
for d, rs in by_dom.items():
    n = len(rs)
    if n < 30:
        continue
    c = Counter(r.get("maturity") for r in rs)
    wf, pr = c.get("workflow", 0), c.get("production", 0)
    if wf >= 10:
        unfinished.append({"domain": d, "n": n, "workflow": wf, "production": pr,
                           "completion_ratio": round(pr / (wf + pr), 2) if (wf + pr) else 0})
unfinished.sort(key=lambda x: x["completion_ratio"])

# ---------- B3. 長尾職業：稀有但認真（樣本少卻已上線） ----------
prof = defaultdict(list)
for r in rows:
    p = (r.get("profession") or "unknown").strip()
    if p and p != "unknown":
        prof[p].append(r)
niche_pros = []
for p, rs in prof.items():
    n = len(rs)
    if 1 <= n <= 8:
        pr = sum(1 for r in rs if r.get("maturity") == "production")
        if pr >= 1:
            niche_pros.append({"profession": p, "n": n, "production": pr,
                               "domains": list({r["domain"] for r in rs}),
                               "pains": [r.get("pain") for r in rs if r.get("pain")][:3],
                               "max_stars": max((r.get("stars") or 0) for r in rs)})
niche_pros.sort(key=lambda x: (-x["production"], -x["max_stars"]))

# ---------- B4. 供給稀薄：領域規模 vs 痛點多樣性 ----------
scarcity = []
for d, rs in by_dom.items():
    pains = [(r.get("pain") or "").strip() for r in rs if r.get("pain")]
    uniq = len(set(pains))
    if len(rs) >= 20:
        scarcity.append({"domain": d, "n": len(rs), "unique_pains": uniq,
                         "diversity": round(uniq / len(rs), 2)})
scarcity.sort(key=lambda x: -x["diversity"])

# ---------- B5. 新進場：近期首見的領域與職業 ----------
recent = defaultdict(Counter)
for r in rows:
    fs = r.get("first_seen")
    if fs:
        recent[fs][r["domain"]] += 1

out = {
    "n_total": N,
    "global_production_pct": round(100 * global_prod, 1),
    "global_task_pct": {k: round(100 * v, 1) for k, v in global_task_pct.items()},
    "A_traction": traction,
    "B1_task_gaps": task_gaps[:25],
    "B2_unfinished": unfinished,
    "B3_niche_professions": niche_pros[:35],
    "B4_pain_diversity": scarcity,
    "B5_by_first_seen": {k: dict(v.most_common(8)) for k, v in sorted(recent.items())[-10:]},
}
json.dump(out, open(os.path.join(ROOT, "corpus", "opportunity.json"), "w"),
          ensure_ascii=False, indent=1)

print(f"機會訊號計算完成（樣本 {N}）")
print(f"\n[A] 上線率高於全體平均（全體 {out['global_production_pct']}%）:")
for t in traction[:6]:
    print(f"   {t['domain']:22s} n={t['n']:4d}  production {t['production_pct']:5.1f}%  ({t['vs_global_production']:+.1f})")
print("\n[B1] 能力缺口（該領域這種任務明顯少於全體水準）:")
for g in task_gaps[:8]:
    print(f"   {g['domain']:22s} 缺 {g['task']:11s} 實際{g['observed']:4d} / 期望{g['expected']:6.1f}  ({g['ratio_vs_global']:.2f}x)")
print("\n[B2] 做一半（完成率最低）:")
for u in unfinished[:6]:
    print(f"   {u['domain']:22s} workflow {u['workflow']:4d} → production {u['production']:4d}  完成率 {u['completion_ratio']}")
