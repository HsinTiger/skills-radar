#!/usr/bin/env python3
"""
build_site.py — 產生知識庫前端頁面 docs/index.html。零 token。

時間軸用 repo_created（repo 建立時間），這是語料裡唯一真實的時間資訊。
注意：這代表「這個 skill 所在的 repo 何時建立」，不是 skill 何時被寫出來，
更不是它何時被使用。頁面上必須標明這個限制。
"""
import json, os, re, html
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")
OPP = os.path.join(ROOT, "corpus", "opportunity.json")
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

rows, rows_all = [], []
for line in open(MASTER, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        r = json.loads(line)
    except Exception:
        continue
    rows_all.append(r)
    if r.get("domain") and r.get("sample") != "targeted-eda":
        rows.append(r)

opp = json.load(open(OPP, encoding="utf-8"))
N = len(rows)

# 語料來自第三方，內容可能出現特定廠商名稱。本頁公開且掛在個人帳號下，
# 為避免成為雇主關聯的推論訊號，顯示層一律遮蔽廠商名，但保留痛點語義。
VENDOR_REDACT = [
    (re.compile(r"瑞昱|Realtek", re.I), "某 IC 廠"),
    (re.compile(r"聯發科|MediaTek", re.I), "某 IC 廠"),
]

def redact(x):
    if not x:
        return x
    for pat, rep in VENDOR_REDACT:
        x = pat.sub(rep, x)
    return x

DOM_ZH = {
    "software-dev": "軟體開發", "ai-agent-tooling": "AI Agent 工具", "devops-infra": "DevOps 基礎設施",
    "design-creative": "設計創意", "personal-productivity": "個人生產力", "security": "資安",
    "ops-admin": "營運行政", "marketing-growth": "行銷成長", "research-academia": "研究學術",
    "finance-investing": "金融投資", "writing-content": "寫作內容", "data-analytics": "資料分析",
    "healthcare-bio": "醫療生技", "legal-compliance": "法務合規", "education-training": "教育訓練",
    "sales-crm": "銷售 CRM", "hardware-eda": "硬體 / EDA", "other": "其他",
}
TASK_ZH = {"generate": "生成", "transform": "轉換", "analyze": "分析", "verify": "驗證",
           "orchestrate": "調度", "retrieve": "檢索", "configure": "配置"}

def bucket(r, mode):
    d = (r.get("repo_created") or "")[:10]
    if len(d) < 10:
        return None
    if mode == "day":
        return d
    if mode == "month":
        return d[:7]
    dt = datetime.strptime(d, "%Y-%m-%d")
    monday = dt - timedelta(days=dt.weekday())
    return monday.strftime("%Y-%m-%d")

def build_view(mode, keep):
    """回傳 {期別: {領域: 件數}}，以及各領域的成長訊號"""
    series = defaultdict(Counter)
    for r in rows:
        b = bucket(r, mode)
        if b:
            series[b][r["domain"]] += 1
    periods = sorted(series)[-keep:]
    totals = {p: sum(series[p].values()) for p in periods}

    # 成長訊號：最近 N 期 vs 前 N 期，佔比變化（用佔比而非絕對數，避免被總量起伏帶著走）
    half = max(1, len(periods) // 2)
    recent, older = periods[-half:], periods[:half]
    rec_n = sum(totals[p] for p in recent) or 1
    old_n = sum(totals[p] for p in older) or 1
    growth = []
    for d in DOM_ZH:
        rc = sum(series[p].get(d, 0) for p in recent)
        oc = sum(series[p].get(d, 0) for p in older)
        if rc + oc < 12:
            continue
        r_share, o_share = 100 * rc / rec_n, 100 * oc / old_n
        growth.append({
            "domain": d, "zh": DOM_ZH[d], "recent": rc, "older": oc,
            "recent_share": round(r_share, 1), "older_share": round(o_share, 1),
            "delta": round(r_share - o_share, 1),
        })
    growth.sort(key=lambda x: -x["delta"])
    return {
        "periods": periods,
        "totals": [totals[p] for p in periods],
        "stack": {d: [series[p].get(d, 0) for p in periods] for d in DOM_ZH},
        "growth": growth,
        "recent_label": f"{recent[0]} ~ {recent[-1]}" if recent else "",
        "older_label": f"{older[0]} ~ {older[-1]}" if older else "",
    }

# ---------- 利基：沒人注意到但做得起來的 ----------
def niches(mode):
    """把結構性缺口 × 該領域近期熱度，挑出「需求在成長、能力卻缺席」的組合"""
    view = build_view(mode, 12 if mode == "month" else 16)
    grow = {g["domain"]: g for g in view["growth"]}
    out = []
    for g in opp["B1_task_gaps"]:
        d = g["domain"]
        gr = grow.get(d)
        out.append({
            "domain": d, "zh": DOM_ZH.get(d, d), "task": g["task"], "task_zh": TASK_ZH[g["task"]],
            "observed": g["observed"], "expected": g["expected"], "ratio": g["ratio_vs_global"],
            "domain_n": g["domain_n"],
            "momentum": gr["delta"] if gr else None,
            "hot": bool(gr and gr["delta"] > 0),
        })
    # 需求在成長 + 能力缺席 = 最值得做
    out.sort(key=lambda x: (x["ratio"], -(x["momentum"] or -99)))
    return out

# ---------- EDA / IC 專區 ----------
CHIP_PAT = re.compile(r"晶片|IC|RTL|UVM|FPGA|時序|閘級|佈線|OpenROAD|驗證平台|覆蓋率|布爾", re.I)
def eda_section():
    neutral_eda = [r for r in rows if r.get("domain") == "hardware-eda"]
    # 過取樣樣本要通過信心門檻才採用（關鍵字正則誤判率實測 75.6%，已棄用）
    eda = [r for r in rows_all if r.get("domain") == "hardware-eda"
           and (r.get("label_source") != "model" or (r.get("domain_conf") or 0) >= 0.6)]
    chip = [r for r in eda if CHIP_PAT.search((r.get("pain") or "") + (r.get("name") or ""))]
    others = [r for r in eda if r not in chip]
    def fmt(rs):
        return [{"stars": r.get("stars") or 0, "task": r.get("task"), "task_zh": TASK_ZH.get(r.get("task"), ""),
                 "maturity": r.get("maturity"), "profession": r.get("profession"),
                 "pain": redact(r.get("pain")), "repo": r.get("repo")}
                for r in sorted(rs, key=lambda x: -(x.get("stars") or 0))]
    tc = Counter(r.get("task") for r in eda)
    mc = Counter(r.get("maturity") for r in eda)
    # 全體 verify 佔比 vs EDA verify 佔比
    return {
        "n": len(eda), "chip_n": len(chip),
        "neutral_n": len(neutral_eda),
        "targeted_n": len(eda) - len(neutral_eda),
        "pct_of_corpus": round(100 * len(neutral_eda) / N, 2),
        "task": {TASK_ZH[k]: v for k, v in tc.most_common() if k},
        "maturity": dict(mc),
        "chip": fmt(chip), "adjacent": fmt(others)[:12],
        "verify_pct": round(100 * tc.get("verify", 0) / len(eda), 1) if eda else 0,
        "global_verify_pct": opp["global_task_pct"]["verify"],
    }

def daily_discovery():
    """每日新發現：first_seen 的逐日增量。這才是真正的「今天有什麼變了」。"""
    # 只算中立樣本：EDA 過取樣是一次性的專案，混進來會讓「每日新發現」看起來暴衝
    disc = defaultdict(Counter)
    for r in rows:
        fs = r.get("first_seen")
        if fs:
            disc[fs][r.get("domain") or "unlabeled"] += 1
    days = sorted(disc)[-30:]
    targeted = Counter()
    for r in rows_all:
        if r.get("sample") == "targeted-eda" and r.get("first_seen"):
            targeted[r["first_seen"]] += 1
    return {"days": days,
            "totals": [sum(disc[d].values()) for d in days],
            "targeted": [targeted.get(d, 0) for d in days],
            "top_domains": {d: dict(disc[d].most_common(6)) for d in days},
            "n_days": len(days)}

def _clean(x):
    x = re.sub(r"\n?-{3,}\s*$", "", (x or "").strip())
    return re.sub(r"\s*-{3,}\s*$", "", x).strip()

def read_summary():
    """把當日的 AI 摘要抓進頁面，讓人不必去 repo 翻 markdown。"""
    import glob as _g
    out = {}
    ins = sorted(_g.glob(os.path.join(ROOT, "research", "insights", "*.md")))
    if ins:
        t = open(ins[-1], encoding="utf-8", errors="replace").read()
        m = re.search(r"## 一句話判斷\s*\n+(.+?)(?=\n##|\Z)", t, re.S)
        sh = re.search(r"## 三、短期看法[^\n]*\n+(.*?)(?=\n## |\Z)", t, re.S)
        md = re.search(r"## 四、中期看法[^\n]*\n+(.*?)(?=\n## |\Z)", t, re.S)
        out["insight"] = {
            "date": os.path.basename(ins[-1])[:-3],
            "headline": _clean(m.group(1).strip() if m else ""),
            "short": _clean(sh.group(1).strip()[:1400] if sh else ""),
            "mid": _clean(md.group(1).strip()[:1400] if md else ""),
        }
    dl = sorted(_g.glob(os.path.join(ROOT, "daily", "*.md")))
    if dl:
        t = open(dl[-1], encoding="utf-8", errors="replace").read()
        m = re.search(r"## 今日一句話\s*\n+(.+?)(?=\n##|\Z)", t, re.S)
        ch = re.search(r"## 🔴 官方變動[^\n]*\n+(.*?)(?=\n## |\Z)", t, re.S)
        out["ecosystem"] = {
            "date": os.path.basename(dl[-1])[:-3],
            "headline": _clean(m.group(1).strip() if m else ""),
            "official": _clean(ch.group(1).strip()[:1200] if ch else ""),
        }
    return out

def eda_gaps():
    """EDA 內部的能力缺口，附真實痛點樣本。只取信心夠或 LLM 標註的硬體樣本。"""
    hw = [r for r in rows_all if r.get("domain") == "hardware-eda"
          and (r.get("label_source") != "model" or (r.get("domain_conf") or 0) >= 0.6)]
    gt = Counter(r.get("task") for r in rows if r.get("task"))
    gn = sum(gt.values()) or 1
    ht = Counter(r.get("task") for r in hw if r.get("task"))
    hn = sum(ht.values()) or 1
    out = []
    for t in TASK_ZH:
        hp = 100 * ht.get(t, 0) / hn
        gp = 100 * gt.get(t, 0) / gn
        samples = [{"pain": redact(r.get("pain")), "stars": r.get("stars") or 0,
                    "name": redact((r.get("name") or "")[:60])}
                   for r in sorted([x for x in hw if x.get("task") == t and x.get("pain")],
                                   key=lambda x: -(x.get("stars") or 0))[:6]]
        out.append({"task": t, "zh": TASK_ZH[t], "hw_pct": round(hp, 1), "global_pct": round(gp, 1),
                    "ratio": round(hp / gp, 2) if gp else 0, "n": ht.get(t, 0), "samples": samples})
    out.sort(key=lambda x: x["ratio"])
    return {"n_hw": len(hw), "tasks": out}

data = {
    "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "n_total": N,
    "global_production_pct": opp["global_production_pct"],
    "global_task_pct": {TASK_ZH[k]: v for k, v in opp["global_task_pct"].items()},
    "day": build_view("day", 30),
    "week": build_view("week", 16),
    "month": build_view("month", 12),
    "discovery": daily_discovery(),
    "summary": read_summary(),
    "schedule": {"hour": 8, "minute": 30, "tz": "Asia/Taipei",
                 "cadence": "每日", "job": "com.hsin.skills-radar"},
    "niche_day": niches("week"),
    "niche_week": niches("week"),
    "niche_month": niches("month"),
    "traction": [{**t, "zh": DOM_ZH.get(t["domain"], t["domain"])} for t in opp["A_traction"]],
    "unfinished": [{**u, "zh": DOM_ZH.get(u["domain"], u["domain"])} for u in opp["B2_unfinished"]],
    "niche_pros": opp["B3_niche_professions"][:18],
    "eda": eda_section(),
    "security": (json.load(open(os.path.join(ROOT, "corpus", "injection_scan.json"), encoding="utf-8"))
                 if os.path.exists(os.path.join(ROOT, "corpus", "injection_scan.json")) else None),
    "eda_gaps": eda_gaps(),
}
json.dump(data, open(os.path.join(DOCS, "data.json"), "w"), ensure_ascii=False, indent=1)

tpl = open(os.path.join(ROOT, "index", "site_template.html"), encoding="utf-8").read()
page = tpl.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(page)
print(f"站台完成：{N} 筆樣本 → docs/index.html ({len(page)//1024} KB)")
print(f"  日級 {len(data['day']['periods'])} 天、週級 {len(data['week']['periods'])} 期、月級 {len(data['month']['periods'])} 期、EDA {data['eda']['n']} 件（其中晶片相關 {data['eda']['chip_n']} 件）")
