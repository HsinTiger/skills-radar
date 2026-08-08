#!/usr/bin/env python3
"""
build_site.py — 產生知識庫前端頁面 docs/index.html。零 token。

時間軸用 repo_created（repo 建立時間），這是語料裡唯一真實的時間資訊。
注意：這代表「這個 skill 所在的 repo 何時建立」，不是 skill 何時被寫出來，
更不是它何時被使用。頁面上必須標明這個限制。
"""
import json, os, re, html, hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from corpus_policy import is_targeted, label_is_eligible, neutral_for, require_model_report_alignment

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
    if neutral_for(r, "domain"):
        rows.append(r)

require_model_report_alignment(rows_all, os.path.join(ROOT, "corpus", "model_report.json"))

catalog_path = os.path.join(ROOT, "corpus", "asic_skill_catalog.json")
asic_catalog = json.load(open(catalog_path, encoding="utf-8"))
master_hasher = hashlib.sha256()
with open(MASTER, "rb") as master_fh:
    for block in iter(lambda: master_fh.read(1024 * 1024), b""):
        master_hasher.update(block)
master_digest = master_hasher.hexdigest()
catalog_snapshot = asic_catalog.get("snapshot", {})
if (asic_catalog.get("status") != "CURRENT_CANDIDATE_CATALOG"
        or catalog_snapshot.get("sha256") != master_digest):
    raise ValueError("ASIC catalog is stale; run bin/build_asic_catalog.py before build_site.py")

ASIC_OWNER_KEYS = {
    (item.get("repo"), item.get("path")): item
    for item in asic_catalog.get("candidates", [])
    if item.get("owner_fit") in {"direct", "supporting"}
    and item.get("hardware_target") in {"asic", "generic"}
}

OWNER_SCOPE_EXCLUDE = re.compile(
    r"\b(?:FPGA|Vivado|Quartus|Vitis|Xilinx|ESP32|STM32|MCU|firmware|PCB|antenna|"
    r"LoRa(?:WAN)?|Zigbee|Bluetooth|UWB|Sub[- ]?GHz)\b|S-parameter|類比|射頻",
    re.I,
)


def owner_scope_row(row):
    text = " ".join(str(row.get(key) or "") for key in ("name", "path", "description", "pain"))
    return not OWNER_SCOPE_EXCLUDE.search(text)

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
    if mode == "quarter":
        return f"{dt.year}-Q{((dt.month - 1) // 3) + 1}"
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
    view = build_view(mode, 12 if mode in {"month", "quarter"} else 16)
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
def eda_section():
    # The owner zone is catalog-routed, not broad hardware keyword search.  This
    # keeps FPGA/embedded/PCB/analog-RF material out even when descriptions also
    # mention RTL or ASIC.
    eda = [
        r for r in rows_all
        if (r.get("repo"), r.get("path")) in ASIC_OWNER_KEYS
        and label_is_eligible(r, "domain")
        and owner_scope_row(r)
    ]
    neutral_eda = [r for r in eda if neutral_for(r, "domain")]
    chip = [r for r in eda if ASIC_OWNER_KEYS[(r.get("repo"), r.get("path"))].get("owner_fit") == "direct"]
    others = [r for r in eda if r not in chip]
    def fmt(rs):
        return [{"stars": r.get("stars") or 0,
                 "task": r.get("task") if label_is_eligible(r, "task") else None,
                 "task_zh": TASK_ZH.get(r.get("task"), "") if label_is_eligible(r, "task") else "",
                 "maturity": r.get("maturity") if label_is_eligible(r, "maturity") else None,
                 "profession": r.get("profession"),
                 "pain": redact(r.get("pain")), "repo": r.get("repo")}
                for r in sorted(rs, key=lambda x: -(x.get("stars") or 0))]
    tc = Counter(r.get("task") for r in eda if label_is_eligible(r, "task"))
    mc = Counter(r.get("maturity") for r in eda if label_is_eligible(r, "maturity"))
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
        if is_targeted(r) and r.get("first_seen"):
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

def read_timescale_summary():
    """Read only validated, period-keyed summaries; never infer success from a scheduled job."""
    history_path = os.path.join(ROOT, "data", "timescale_summaries.json")
    status_path = os.path.join(ROOT, "data", "timescale_summary_status.json")
    history = {}
    status = {"status": "NOT_RUN", "updated_periods": []}
    if os.path.exists(history_path):
        history = json.load(open(history_path, encoding="utf-8"))
    if os.path.exists(status_path):
        status = json.load(open(status_path, encoding="utf-8"))
    periods = history.get("periods", {})
    return {
        "latest": history.get("latest", {}),
        "status": status,
        "period_counts": {scale: len(records) for scale, records in periods.items()},
    }

def read_latest_editorial():
    """Expose only validated local editorial metadata; the renderer owns article HTML."""
    import glob as _g
    sources = sorted(_g.glob(os.path.join(ROOT, "research", "editorials", "*.md")), reverse=True)
    if not sources:
        return None
    source = sources[0]
    date = os.path.basename(source)[:-3]
    first = open(source, encoding="utf-8", errors="replace").readline().strip()
    title = first[2:].strip() if first.startswith("# ") else f"Skills Radar 觀點 — {date}"
    return {"date": date, "title": title, "href": f"editorials/{date}.html"}

def eda_gaps():
    """Owner-scoped ASIC/RTL ability gaps; excluded hardware never enters."""
    hw = [
        r for r in rows_all
        if (r.get("repo"), r.get("path")) in ASIC_OWNER_KEYS
        and label_is_eligible(r, "domain")
        and owner_scope_row(r)
    ]
    gt = Counter(r.get("task") for r in rows if label_is_eligible(r, "task"))
    gn = sum(gt.values()) or 1
    ht = Counter(r.get("task") for r in hw if label_is_eligible(r, "task"))
    hn = sum(ht.values()) or 1
    out = []
    for t in TASK_ZH:
        hp = 100 * ht.get(t, 0) / hn
        gp = 100 * gt.get(t, 0) / gn
        samples = [{"pain": redact(r.get("pain")), "stars": r.get("stars") or 0,
                    "name": redact((r.get("name") or "")[:60])}
                   for r in sorted([x for x in hw if x.get("task") == t and x.get("pain")
                                    and label_is_eligible(x, "task")],
                                   key=lambda x: -(x.get("stars") or 0))[:6]]
        out.append({"task": t, "zh": TASK_ZH[t], "hw_pct": round(hp, 1), "global_pct": round(gp, 1),
                    "ratio": round(hp / gp, 2) if gp else 0, "n": ht.get(t, 0), "samples": samples})
    out.sort(key=lambda x: x["ratio"])
    return {"n_hw": len(hw), "tasks": out}

data = {
    "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "n_total": N,
    "eligibility": opp.get("eligibility", {}),
    "global_production_pct": opp["global_production_pct"],
    "global_task_pct": {TASK_ZH[k]: v for k, v in opp["global_task_pct"].items()},
    "day": build_view("day", 30),
    "week": build_view("week", 16),
    "month": build_view("month", 12),
    "quarter": build_view("quarter", 12),
    "discovery": daily_discovery(),
    "summary": read_summary(),
    "timescale_summary": read_timescale_summary(),
    "editorial": read_latest_editorial(),
    "pipeline_health": (json.load(open(os.path.join(ROOT, "data", "pipeline_health.json"), encoding="utf-8"))
                        if os.path.exists(os.path.join(ROOT, "data", "pipeline_health.json")) else None),
    "schedule": {"hour": 8, "minute": 30, "tz": "Asia/Taipei",
                 "cadence": "每日", "job": "com.hsin.skills-radar"},
    "niche_day": niches("week"),
    "niche_week": niches("week"),
    "niche_month": niches("month"),
    "niche_quarter": niches("quarter"),
    "traction": [{**t, "zh": DOM_ZH.get(t["domain"], t["domain"])} for t in opp["A_traction"]],
    "unfinished": [{**u, "zh": DOM_ZH.get(u["domain"], u["domain"])} for u in opp["B2_unfinished"]],
    "niche_pros": opp["B3_niche_professions"][:18],
    "eda": eda_section(),
    "security": (json.load(open(os.path.join(ROOT, "corpus", "injection_scan.json"), encoding="utf-8"))
                 if os.path.exists(os.path.join(ROOT, "corpus", "injection_scan.json")) else None),
    "eda_gaps": eda_gaps(),
}
with open(os.path.join(DOCS, "data.json"), "w", encoding="utf-8", newline="\n") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=1)
    fh.write("\n")

tpl = open(os.path.join(ROOT, "index", "site_template.html"), encoding="utf-8").read()
page = tpl.replace("/*__DATA__*/", json.dumps(data, ensure_ascii=False))
open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(page)
print(f"站台完成：{N} 筆樣本 → docs/index.html ({len(page)//1024} KB)")
print(f"  日級 {len(data['day']['periods'])} 天、週級 {len(data['week']['periods'])} 期、月級 {len(data['month']['periods'])} 期、季級 {len(data['quarter']['periods'])} 期、EDA {data['eda']['n']} 件（其中晶片相關 {data['eda']['chip_n']} 件）")
