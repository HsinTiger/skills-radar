#!/usr/bin/env python3
"""Ingest corpus evidence into cumulative per-domain wiki pages.

Only aggregate values enter the wiki.  Raw third-party text is deliberately
excluded.  Re-running an unchanged date is idempotent; changing evidence on an
already ingested date requires ``--revision-note`` so corrections are explicit.
"""

import argparse
import hashlib
import html
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from corpus_policy import (
    CONF_MIN, label_is_eligible, neutral_for, require_model_report_alignment,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")
OPPORTUNITY = os.path.join(ROOT, "corpus", "opportunity.json")
HISTORY = os.path.join(ROOT, "data", "wiki_history.json")
RESEARCH_WIKI = os.path.join(ROOT, "research", "wiki")
DOCS_WIKI = os.path.join(ROOT, "docs", "wiki")

DOM_ZH = {
    "software-dev": "軟體開發", "ai-agent-tooling": "AI Agent 工具",
    "devops-infra": "DevOps 基礎設施", "design-creative": "設計創意",
    "personal-productivity": "個人生產力", "security": "資安",
    "ops-admin": "營運行政", "marketing-growth": "行銷成長",
    "research-academia": "研究學術", "finance-investing": "金融投資",
    "writing-content": "寫作內容", "data-analytics": "資料分析",
    "healthcare-bio": "醫療生技", "legal-compliance": "法務合規",
    "education-training": "教育訓練", "sales-crm": "銷售 CRM",
    "hardware-eda": "硬體 / EDA", "other": "其他",
}
TASK_ZH = {
    "generate": "生成", "transform": "轉換", "analyze": "分析",
    "verify": "驗證", "orchestrate": "調度", "retrieve": "檢索",
    "configure": "配置",
}
OWNER_START = "<!-- OWNER-NOTES:START -->"
OWNER_END = "<!-- OWNER-NOTES:END -->"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path=MASTER):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def pct(counter, denominator):
    denominator = denominator or 1
    return {key: round(100 * value / denominator, 1)
            for key, value in counter.most_common() if key}


def build_snapshot(rows, opportunity, snapshot_date, provenance=None):
    eligible = [row for row in rows if neutral_for(row, "domain")]
    by_domain = defaultdict(list)
    for row in eligible:
        by_domain[row["domain"]].append(row)

    gaps_by_domain = defaultdict(list)
    for gap in opportunity.get("B1_task_gaps", []):
        gaps_by_domain[gap.get("domain")].append({
            "task": gap.get("task"),
            "observed": gap.get("observed"),
            "expected": gap.get("expected"),
            "ratio_vs_global": gap.get("ratio_vs_global"),
        })

    domains = {}
    total = len(eligible) or 1
    for domain in DOM_ZH:
        domain_rows = by_domain.get(domain, [])
        if not domain_rows:
            continue
        task_rows = [r for r in domain_rows if label_is_eligible(r, "task")]
        maturity_rows = [r for r in domain_rows if label_is_eligible(r, "maturity")]
        target_rows = [r for r in domain_rows if label_is_eligible(r, "target")]
        task_count = Counter(r.get("task") for r in task_rows)
        maturity_count = Counter(r.get("maturity") for r in maturity_rows)
        target_count = Counter(r.get("target") for r in target_rows)
        domains[domain] = {
            "name_zh": DOM_ZH[domain],
            "n": len(domain_rows),
            "share_pct": round(100 * len(domain_rows) / total, 2),
            "coverage": {
                "task": len(task_rows),
                "maturity": len(maturity_rows),
                "target": len(target_rows),
                "model_domain": sum(r.get("label_source") == "model" for r in domain_rows),
                "human_or_legacy_domain": sum(r.get("label_source") != "model" for r in domain_rows),
            },
            "task_pct": pct(task_count, len(task_rows)),
            "maturity_pct": pct(maturity_count, len(maturity_rows)),
            "production_pct": round(
                100 * maturity_count.get("production", 0) / (len(maturity_rows) or 1), 1
            ),
            "agent_target_pct": round(
                100 * target_count.get("agent", 0) / (len(target_rows) or 1), 1
            ),
            "gaps": gaps_by_domain.get(domain, []),
        }

    snapshot = {
        "date": snapshot_date,
        "revision": 1,
        "revision_note": "initial ingest",
        "policy": {
            "sample": "neutral only; sample missing, empty, or neutral",
            "targeted": "all targeted-* excluded from population estimates",
            "model_conf_min": CONF_MIN,
            "raw_third_party_text": "excluded",
        },
        "overall": {
            "n_total": len(eligible),
            "global_production_pct": opportunity.get("global_production_pct"),
            "global_task_pct": opportunity.get("global_task_pct", {}),
        },
        "domains": domains,
        "provenance": provenance or {},
    }
    return snapshot


def measurement(snapshot):
    return {
        "policy": snapshot.get("policy"),
        "overall": snapshot.get("overall"),
        "domains": snapshot.get("domains"),
        "provenance": snapshot.get("provenance"),
    }


def append_snapshot(history, snapshot, revision_note=None):
    snapshots = history.setdefault("snapshots", [])
    if not snapshots:
        snapshots.append(snapshot)
        return True

    latest = snapshots[-1]
    if snapshot["date"] < latest["date"]:
        raise ValueError(
            f"snapshot date {snapshot['date']} is older than latest {latest['date']}"
        )
    if snapshot["date"] == latest["date"]:
        if measurement(snapshot) == measurement(latest):
            return False
        if not revision_note:
            raise ValueError(
                "same-date evidence changed; rerun with --revision-note to preserve the correction trail"
            )
        revisions = [s.get("revision", 1) for s in snapshots if s["date"] == snapshot["date"]]
        snapshot["revision"] = max(revisions) + 1
        snapshot["revision_note"] = revision_note
    else:
        snapshot["revision"] = 1
        snapshot["revision_note"] = revision_note or "scheduled evidence ingest"

    snapshot["change"] = {
        "n_total_delta": snapshot["overall"]["n_total"] - latest["overall"]["n_total"]
    }
    snapshots.append(snapshot)
    return True


def load_history(path=HISTORY):
    if not os.path.exists(path):
        return {"schema_version": 1, "snapshots": []}
    with open(path, encoding="utf-8") as fh:
        history = json.load(fh)
    if history.get("schema_version") != 1 or not isinstance(history.get("snapshots"), list):
        raise ValueError("unsupported or malformed wiki history")
    return history


def owner_notes(path):
    if not os.path.exists(path):
        return (
            f"{OWNER_START}\n"
            "尚無 owner 判斷；數值之外的解讀一律標為 `UNKNOWN`。\n"
            f"{OWNER_END}"
        )
    text = open(path, encoding="utf-8").read()
    start = text.find(OWNER_START)
    end = text.find(OWNER_END)
    if start < 0 or end < start:
        raise ValueError(f"owner notes markers missing or malformed: {path}")
    return text[start:end + len(OWNER_END)]


def domain_history(history, domain):
    out = []
    for snapshot in history["snapshots"]:
        metrics = snapshot.get("domains", {}).get(domain)
        if metrics:
            out.append((snapshot, metrics))
    return out


def render_domain_markdown(domain, history):
    entries = domain_history(history, domain)
    latest_snapshot, latest = entries[-1]
    path = os.path.join(RESEARCH_WIKI, f"{domain}.md")
    notes = owner_notes(path)
    top_tasks = sorted(latest["task_pct"].items(), key=lambda item: -item[1])[:5]
    gaps = latest.get("gaps", [])

    lines = [
        f"# {latest['name_zh']} (`{domain}`)", "",
        "> 這是累積式實體頁面，不是每日重新生成的敘事。自動區只包含聚合值；owner notes 會跨 ingest 保留。",
        "", "## Owner notes", "", notes, "", "## Current evidence", "",
        f"- `PROVEN` 中立且可用的 domain 樣本：**{latest['n']:,}**（母體 {latest['share_pct']:.2f}%）",
        f"- `PROVEN` production：**{latest['production_pct']:.1f}%**（maturity 有效樣本 {latest['coverage']['maturity']:,}）",
        f"- `PROVEN` agent target：**{latest['agent_target_pct']:.1f}%**（target 有效樣本 {latest['coverage']['target']:,}）",
        f"- `PROVEN` 最新 evidence：{latest_snapshot['date']} r{latest_snapshot.get('revision', 1)}",
        "- `UNKNOWN` 私有／企業內 skill 的採用比例、實際使用頻率與業務成效。",
        "", "### Task distribution", "",
        "| task | share |", "|---|---:|",
    ]
    for task, share in top_tasks:
        lines.append(f"| {TASK_ZH.get(task, task)} (`{task}`) | {share:.1f}% |")
    lines.extend(["", "### Structural signals", ""])
    if gaps:
        lines.extend(["| missing task | observed / expected | ratio |", "|---|---:|---:|"])
        for gap in gaps:
            lines.append(
                f"| {TASK_ZH.get(gap['task'], gap['task'])} (`{gap['task']}`) | "
                f"{gap['observed']} / {gap['expected']} | {gap['ratio_vs_global']:.2f}x |"
            )
        lines.append("")
        lines.append(
            "`PROVEN` 僅限 observed/expected 計算；把缺口解讀成產品機會仍是 `ASSUMED`，需 owner 判斷。"
        )
    else:
        lines.append("目前沒有符合訊號門檻的 task gap；這不等於 `PROVEN` 沒有機會。")

    lines.extend([
        "", "## Evidence history", "",
        "| date | rev | n | corpus share | production | total delta | note |",
        "|---|---:|---:|---:|---:|---:|---|",
    ])
    for snapshot, metrics in entries:
        delta = snapshot.get("change", {}).get("n_total_delta", 0)
        note = str(snapshot.get("revision_note", "")).replace("|", "\\|")
        lines.append(
            f"| {snapshot['date']} | {snapshot.get('revision', 1)} | {metrics['n']:,} | "
            f"{metrics['share_pct']:.2f}% | {metrics['production_pct']:.1f}% | "
            f"{delta:+d} | {note} |"
        )
    lines.extend([
        "", "## Evidence contract", "",
        f"- 中立抽樣限定；所有 `targeted-*` 排除於母體統計。",
        f"- 模型欄位信心門檻：`{CONF_MIN}`；各欄位分開判定。",
        "- Wiki 不收錄第三方原文；質性例子須另經 injection 與 privacy 檢查。",
        f"- master SHA-256：`{latest_snapshot.get('provenance', {}).get('master_sha256', 'UNKNOWN')}`",
        "", "[返回 Wiki index](README.md)", "",
    ])
    return "\n".join(lines)


def render_research(history):
    os.makedirs(RESEARCH_WIKI, exist_ok=True)
    latest = history["snapshots"][-1]
    rows = sorted(latest["domains"].items(), key=lambda item: -item[1]["n"])
    index = [
        "# Skills Radar Domain Wiki", "",
        "> Canonical cumulative entity pages. Aggregate evidence only; no raw third-party text.", "",
        f"Latest evidence: **{latest['date']} r{latest.get('revision', 1)}** · neutral n={latest['overall']['n_total']:,}",
        "", "| domain | n | share | production |", "|---|---:|---:|---:|",
    ]
    for domain, metrics in rows:
        index.append(
            f"| [{metrics['name_zh']}]({domain}.md) | {metrics['n']:,} | "
            f"{metrics['share_pct']:.2f}% | {metrics['production_pct']:.1f}% |"
        )
        text = render_domain_markdown(domain, history)
        with open(os.path.join(RESEARCH_WIKI, f"{domain}.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    with open(os.path.join(RESEARCH_WIKI, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(index) + "\n")


CSS = """
:root{--bg:#fbfaf8;--panel:#fff;--line:#e6e2db;--ink:#1c1b19;--dim:#6b6660;--accent:#b4501e}
@media(prefers-color-scheme:dark){:root{--bg:#151413;--panel:#1e1d1b;--line:#332f2b;--ink:#ece8e2;--dim:#9c958c;--accent:#e08050}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;line-height:1.65}
main{max-width:900px;margin:auto;padding:2rem 1.2rem 5rem}a{color:var(--accent)}h1{border-bottom:2px solid var(--ink);padding-bottom:.7rem}.meta,.unknown{color:var(--dim)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:.8rem}.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:1rem;text-decoration:none;color:inherit}.card b{display:block}.card span{font-size:.85rem;color:var(--dim)}
table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{padding:.5rem;border-bottom:1px solid var(--line);text-align:left}td.num,th.num{text-align:right}code{font-size:.88em}nav{margin-bottom:1rem}
""".strip()


def html_shell(title, body):
    return (
        "<!doctype html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{html.escape(title)}</title><link rel=\"stylesheet\" href=\"style.css\"></head>"
        f"<body><main>{body}</main></body></html>"
    )


def render_docs(history):
    os.makedirs(DOCS_WIKI, exist_ok=True)
    latest = history["snapshots"][-1]
    rows = sorted(latest["domains"].items(), key=lambda item: -item[1]["n"])
    cards = []
    for domain, metrics in rows:
        cards.append(
            f'<a class="card" href="{html.escape(domain)}.html"><b>{html.escape(metrics["name_zh"])}</b>'
            f'<span>n={metrics["n"]:,} · {metrics["share_pct"]:.2f}% · production {metrics["production_pct"]:.1f}%</span></a>'
        )
    body = (
        '<nav><a href="../index.html">← Skills Radar</a></nav>'
        '<h1>Domain Wiki</h1>'
        '<p>每個領域一頁，累積 evidence history；不收錄第三方原文。</p>'
        f'<p class="meta">最新證據 {html.escape(latest["date"])} r{latest.get("revision", 1)} · '
        f'neutral n={latest["overall"]["n_total"]:,}</p><div class="grid">{"".join(cards)}</div>'
    )
    with open(os.path.join(DOCS_WIKI, "index.html"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html_shell("Skills Radar Domain Wiki", body))
    with open(os.path.join(DOCS_WIKI, "style.css"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(CSS + "\n")

    for domain, metrics in rows:
        entries = domain_history(history, domain)
        task_rows = "".join(
            f"<tr><td>{html.escape(TASK_ZH.get(task, task))}</td><td class=\"num\">{share:.1f}%</td></tr>"
            for task, share in sorted(metrics["task_pct"].items(), key=lambda item: -item[1])
        )
        history_rows = "".join(
            f"<tr><td>{html.escape(snapshot['date'])}</td><td class=\"num\">{snapshot.get('revision', 1)}</td>"
            f"<td class=\"num\">{value['n']:,}</td><td class=\"num\">{value['share_pct']:.2f}%</td>"
            f"<td class=\"num\">{value['production_pct']:.1f}%</td></tr>"
            for snapshot, value in entries
        )
        body = (
            '<nav><a href="index.html">← Domain Wiki</a> · <a href="../index.html">Skills Radar</a></nav>'
            f'<h1>{html.escape(metrics["name_zh"])} <code>{html.escape(domain)}</code></h1>'
            f'<p><b>PROVEN</b> neutral n={metrics["n"]:,}（母體 {metrics["share_pct"]:.2f}%）；'
            f'production {metrics["production_pct"]:.1f}%。</p>'
            '<p class="unknown"><b>UNKNOWN</b> 私有／企業內 skill 採用比例、實際使用頻率與業務成效。</p>'
            '<h2>Task distribution</h2><table><thead><tr><th>task</th><th class="num">share</th></tr></thead>'
            f'<tbody>{task_rows}</tbody></table><h2>Evidence history</h2>'
            '<table><thead><tr><th>date</th><th class="num">rev</th><th class="num">n</th>'
            '<th class="num">share</th><th class="num">production</th></tr></thead>'
            f'<tbody>{history_rows}</tbody></table><p class="meta">所有 targeted-* 已排除；model confidence ≥ {CONF_MIN}。</p>'
        )
        with open(os.path.join(DOCS_WIKI, f"{domain}.html"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(html_shell(f"{metrics['name_zh']} — Skills Radar", body))


def parse_args():
    taipei = timezone(timedelta(hours=8))
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(taipei).date().isoformat())
    parser.add_argument("--revision-note")
    return parser.parse_args()


def main():
    args = parse_args()
    rows = load_rows()
    require_model_report_alignment(rows, os.path.join(ROOT, "corpus", "model_report.json"))
    with open(OPPORTUNITY, encoding="utf-8") as fh:
        opportunity = json.load(fh)
    provenance = {
        "master_sha256": sha256_file(MASTER),
        "opportunity_sha256": sha256_file(OPPORTUNITY),
        "master_rows": len(rows),
    }
    snapshot = build_snapshot(rows, opportunity, args.date, provenance)
    history = load_history()
    changed = append_snapshot(history, snapshot, args.revision_note)
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    if changed:
        with open(HISTORY, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(history, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    render_research(history)
    render_docs(history)
    latest = history["snapshots"][-1]
    print(
        f"Wiki {'ingested' if changed else 'unchanged'}: {latest['date']} "
        f"r{latest.get('revision', 1)}, {len(latest['domains'])} domains, "
        f"neutral n={latest['overall']['n_total']}"
    )


if __name__ == "__main__":
    main()
