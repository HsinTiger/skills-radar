#!/usr/bin/env python3
"""Cadence-aware AI summaries for the Skills Radar historical corpus.

One daily dispatcher updates only completed periods that are missing:
day (previous day), week (previous Mon-Sun), month (previous calendar
month), and quarter (previous calendar quarter).  Each completed period has one
record keyed by period id.  A missed Mac run is retried, and records that no
longer satisfy the current reader-safety contract are rewritten instead of
remaining permanently publishable; Git history preserves the earlier version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from corpus_policy import label_is_eligible, neutral_for


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "corpus" / "master.jsonl"
MODEL_REPORT = ROOT / "corpus" / "model_report.json"
TAXONOMY_REPORT = ROOT / "corpus" / "asic_taxonomy_report.json"
RECOMMENDATIONS = ROOT / "corpus" / "daily_skill_recommendations.json"
EVIDENCE_OUT = ROOT / "corpus" / "timescale_evidence.json"
HISTORY_OUT = ROOT / "data" / "timescale_summaries.json"
STATUS_OUT = ROOT / "data" / "timescale_summary_status.json"
PROMPT = ROOT / "index" / "prompt_timescale_summary.txt"

SCALES = ("day", "week", "month", "quarter")
SCALE_ZH = {"day": "日", "week": "週", "month": "月", "quarter": "季"}
DOMAIN_ZH = {
    "software-dev": "軟體開發", "ai-agent-tooling": "AI Agent 工具",
    "devops-infra": "DevOps 基礎設施", "design-creative": "設計創意",
    "personal-productivity": "個人生產力", "security": "資安",
    "ops-admin": "營運行政", "marketing-growth": "行銷成長",
    "research-academia": "研究學術", "finance-investing": "財經投資",
    "writing-content": "寫作內容", "data-analytics": "資料分析",
    "healthcare-bio": "醫療生技", "legal-compliance": "法務合規",
    "education-training": "教育訓練", "sales-crm": "銷售 CRM",
    "hardware-eda": "硬體 / EDA", "other": "其他",
}
TASK_ZH = {
    "generate": "生成", "transform": "轉換", "analyze": "分析", "verify": "驗證",
    "orchestrate": "調度", "retrieve": "檢索", "configure": "配置",
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def master_freshness(rows: list[dict], report: dict, master_path: Path) -> dict:
    actual_seed = sum(bool(r.get("domain")) and r.get("label_source") != "model" for r in rows)
    actual_model = sum(r.get("label_source") == "model" for r in rows)
    expected_seed = report.get("n_seed")
    expected_model = report.get("n_predicted")
    current = actual_seed == expected_seed and actual_model == expected_model
    return {
        "status": "CURRENT" if current else "STALE",
        "master_sha256": hashlib.sha256(master_path.read_bytes()).hexdigest(),
        "actual_seed": actual_seed,
        "actual_model": actual_model,
        "expected_seed": expected_seed,
        "expected_model": expected_model,
    }


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _quarter_start(d: date) -> date:
    return date(d.year, ((d.month - 1) // 3) * 3 + 1, 1)


def latest_complete_period(run_date: date, scale: str) -> dict:
    if scale == "day":
        start = end = run_date - timedelta(days=1)
        period_id = start.isoformat()
    elif scale == "week":
        this_monday = run_date - timedelta(days=run_date.weekday())
        end = this_monday - timedelta(days=1)
        start = end - timedelta(days=6)
        iso_year, iso_week, _ = start.isocalendar()
        period_id = f"{iso_year}-W{iso_week:02d}"
    elif scale == "month":
        end = _month_start(run_date) - timedelta(days=1)
        start = _month_start(end)
        period_id = start.strftime("%Y-%m")
    elif scale == "quarter":
        end = _quarter_start(run_date) - timedelta(days=1)
        start = _quarter_start(end)
        period_id = f"{start.year}-Q{((start.month - 1) // 3) + 1}"
    else:
        raise ValueError(f"unsupported scale: {scale}")
    return {"scale": scale, "period_id": period_id, "start": start.isoformat(), "end": end.isoformat()}


def next_period(period: dict) -> dict:
    end = date.fromisoformat(period["end"])
    scale = period["scale"]
    start = end + timedelta(days=1)
    if scale == "day":
        next_end = start
        period_id = start.isoformat()
    elif scale == "week":
        next_end = start + timedelta(days=6)
        iso_year, iso_week, _ = start.isocalendar()
        period_id = f"{iso_year}-W{iso_week:02d}"
    elif scale == "month":
        following = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month + 1, 1)
        next_end = following - timedelta(days=1)
        period_id = start.strftime("%Y-%m")
    elif scale == "quarter":
        month = start.month + 3
        following = date(start.year + (month > 12), month - 12 if month > 12 else month, 1)
        next_end = following - timedelta(days=1)
        period_id = f"{start.year}-Q{((start.month - 1) // 3) + 1}"
    else:
        raise ValueError(f"unsupported scale: {scale}")
    return {"scale": scale, "period_id": period_id, "start": start.isoformat(), "end": next_end.isoformat()}


def previous_period(period: dict) -> dict:
    start = date.fromisoformat(period["start"])
    scale = period["scale"]
    if scale == "day":
        anchor = start
    elif scale == "week":
        anchor = start
    elif scale == "month":
        anchor = start
    else:
        anchor = start
    return latest_complete_period(anchor, scale)


def due_periods(history: dict, run_date: date, max_periods: int = 31) -> tuple[list[dict], dict]:
    due = []
    backlog = {}
    periods_by_scale = history.get("periods", {})
    for scale in SCALES:
        latest = latest_complete_period(run_date, scale)
        existing = periods_by_scale.get(scale, {})
        successful = [r for r in existing.values() if r.get("status") == "AI_GENERATED"]
        if not successful:
            candidates = [latest]
        else:
            last = max(successful, key=lambda r: r["period"]["end"])["period"]
            candidates = []
            cursor = next_period(last)
            while cursor["end"] <= latest["end"]:
                if cursor["period_id"] not in existing:
                    candidates.append(cursor)
                cursor = next_period(cursor)
        backlog[scale] = max(0, len(candidates) - max_periods)
        due.extend(candidates[:max_periods])
    due.sort(key=lambda p: (p["end"], SCALES.index(p["scale"])))
    return due, backlog


def _in_range(value, start: str, end: str) -> bool:
    if not value:
        return False
    day = str(value)[:10]
    return len(day) == 10 and start <= day <= end


def _eligible_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if neutral_for(r, "domain")]


def _mix(rows: list[dict], field: str, labels: dict | None = None, limit: int = 8) -> list[dict]:
    counts = Counter(r.get(field) for r in rows if label_is_eligible(r, field))
    total = sum(counts.values()) or 1
    out = []
    for key, count in counts.most_common(limit):
        out.append({
            "key": key, "label": (labels or {}).get(key, key), "count": count,
            "share_pct": round(100 * count / total, 1),
        })
    return out


def _share_map(rows: list[dict], field: str) -> tuple[Counter, int]:
    counts = Counter(r.get(field) for r in rows if label_is_eligible(r, field))
    return counts, sum(counts.values())


def _shifts(current: list[dict], previous: list[dict], field: str, labels: dict | None = None) -> list[dict]:
    cc, cn = _share_map(current, field)
    pc, pn = _share_map(previous, field)
    if not cn or not pn:
        return []
    out = []
    for key in sorted(set(cc) | set(pc)):
        if cc[key] + pc[key] < 5:
            continue
        cur = 100 * cc[key] / cn
        prev = 100 * pc[key] / pn
        out.append({
            "key": key, "label": (labels or {}).get(key, key),
            "current_count": cc[key], "previous_count": pc[key],
            "current_share_pct": round(cur, 1), "previous_share_pct": round(prev, 1),
            "delta_pp": round(cur - prev, 1),
        })
    out.sort(key=lambda x: -abs(x["delta_pp"]))
    return out[:10]


def _entropy(rows: list[dict], field: str) -> dict:
    counts, total = _share_map(rows, field)
    if total <= 1 or len(counts) <= 1:
        return {"normalized": 0.0, "categories": len(counts), "n": total}
    raw = -sum((n / total) * math.log(n / total) for n in counts.values())
    return {"normalized": round(raw / math.log(len(counts)), 3), "categories": len(counts), "n": total}


def _proxy(rows: list[dict], field: str, value: str) -> dict:
    eligible = [r for r in rows if label_is_eligible(r, field)]
    hits = sum(r.get(field) == value for r in eligible)
    return {"count": hits, "eligible_n": len(eligible), "pct": round(100 * hits / len(eligible), 1) if eligible else None}


def _asic_focus(rows: list[dict], taxonomy_report: dict) -> dict:
    from asic_taxonomy import classify_row

    hw = [r for r in rows if r.get("domain") == "hardware-eda"]
    fit, stages, wifi, targets = Counter(), Counter(), Counter(), Counter()
    for row in hw:
        try:
            result = classify_row(row)
        except ValueError:
            continue
        fit[result["owner_fit"]] += 1
        targets[result["hardware_target"]] += 1
        stages.update(result["asic_stages"])
        wifi.update(result["wifi_areas"])
    validation = taxonomy_report.get("validation") or taxonomy_report.get("snapshot", {}).get("taxonomy_validation", {})
    return {
        "hardware_eda_n": len(hw),
        "owner_fit_provisional": dict(fit),
        "hardware_target_provisional": dict(targets),
        "top_asic_stages": [{"key": k, "count": v} for k, v in stages.most_common(8)],
        "wifi_areas": [{"key": k, "count": v} for k, v in wifi.most_common(8)],
        "taxonomy_validation": validation.get("status") or taxonomy_report.get("status", "UNKNOWN"),
        "scope_note": "deterministic secondary taxonomy; FPGA/embedded/PCB/analog-RF are not owner-direct",
    }


def _finance_focus(rows: list[dict], recommendations: dict) -> dict:
    finance = [r for r in rows if r.get("domain") == "finance-investing"]
    latest = recommendations.get("categories", {}).get("finance-investing", {})
    rec_counts = Counter(r.get("recommendation") for r in latest.get("recommendations", []))
    return {
        "finance_n": len(finance),
        "task_mix": _mix(finance, "task", TASK_ZH),
        "maturity_mix": _mix(finance, "maturity"),
        "current_recommendation_states": dict(rec_counts),
        "boundary": "research only; no trade execution, broker/wallet credentials, or profit claims",
    }


def build_period_evidence(rows: list[dict], period: dict, freshness: dict,
                          taxonomy_report: dict, recommendations: dict) -> dict:
    neutral = _eligible_rows(rows)
    previous = previous_period(period)
    archive = [r for r in neutral if _in_range(r.get("repo_created"), period["start"], period["end"])]
    archive_prev = [r for r in neutral if _in_range(r.get("repo_created"), previous["start"], previous["end"])]
    discovered = [r for r in neutral if _in_range(r.get("first_seen"), period["start"], period["end"])]
    discovered_prev = [r for r in neutral if _in_range(r.get("first_seen"), previous["start"], previous["end"])]
    return {
        "scale": period["scale"],
        "scale_zh": SCALE_ZH[period["scale"]],
        "period": period,
        "previous_period": previous,
        "time_contract": {
            "discovery_clock": "first_seen: radar first observed the skill; only valid after monitoring began",
            "archive_clock": "repo_created: repository creation cohort, not skill creation or usage time",
            "completeness": "recent repo_created cohorts are search-index incomplete; interpret the newest period cautiously",
        },
        "freshness": freshness,
        "evidence": {
            "E1_sample": {
                "archive_n": len(archive), "archive_previous_n": len(archive_prev),
                "discovered_n": len(discovered), "discovered_previous_n": len(discovered_prev),
            },
            "E2_domain_mix": _mix(archive, "domain", DOMAIN_ZH),
            "E3_domain_shifts": _shifts(archive, archive_prev, "domain", DOMAIN_ZH),
            "E4_task_mix": _mix(archive, "task", TASK_ZH),
            "E5_task_shifts": _shifts(archive, archive_prev, "task", TASK_ZH),
            "E6_maturity": {
                "mix": _mix(archive, "maturity"),
                "production_document_proxy": _proxy(archive, "maturity", "production"),
                "agent_target_proxy": _proxy(archive, "target", "agent"),
                "warning": "document labels are intent/proxy, not deployment or outcome verification",
            },
            "E7_diversity": {
                "domain_entropy": _entropy(archive, "domain"),
                "task_entropy": _entropy(archive, "task"),
            },
            "E8_eda_ic": _asic_focus(archive, taxonomy_report),
            "E9_finance": _finance_focus(archive, recommendations),
            "E10_quality": {
                "neutral_population_only": True,
                "targeted_rows_excluded": True,
                "archive_domain_eligible_n": len(archive),
                "comparison_domain_eligible_n": len(archive_prev),
                "minimum_shift_support": 5,
            },
        },
    }


NARRATIVE_FIELDS = (
    "headline", "executive_summary", "eda_ic_readout", "finance_readout", "contrarian_view",
)
LIST_FIELDS = ("structural_changes", "actions", "falsifiers", "caveats")
INTERNAL_NARRATIVE = re.compile(
    r"\b(?:E(?:10|[1-9])|archive_n|discovered_n|discovered_previous_n|domain mix|task mix|"
    r"maturity mix|production_document_proxy|agent_target_proxy|hardware_eda_n|finance_n|"
    r"evidence_ids|AI_GENERATED|EDA_IC|cohort|proxy|entropy|[A-Za-z]+_[A-Za-z0-9_]+)\b",
    re.I,
)
READER_JARGON = re.compile(
    r"\b(?:repo(?:sitory)?|confidence|completeness|taxonomy|validation|signoff|golden|"
    r"production|workflow|toy|owner(?:-direct)?|front-end|DevOps|pct|pp)\b",
    re.I,
)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def validate_ai_output(raw: str, due: list[dict]) -> list[dict]:
    doc = json.loads(_strip_fence(raw))
    summaries = doc.get("summaries") if isinstance(doc, dict) else None
    if not isinstance(summaries, list):
        raise ValueError("AI output must contain summaries[]")
    expected = {(p["scale"], p["period_id"]) for p in due}
    got = {(s.get("scale"), s.get("period_id")) for s in summaries if isinstance(s, dict)}
    if got != expected:
        raise ValueError(f"AI output periods mismatch: expected={sorted(expected)} got={sorted(got)}")
    for summary in summaries:
        if summary.get("confidence") not in {"HIGH", "MEDIUM", "LOW"}:
            raise ValueError("confidence must be HIGH/MEDIUM/LOW")
        for field in NARRATIVE_FIELDS:
            value = summary.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"missing narrative field: {field}")
            if len(value) > 900:
                raise ValueError(f"narrative field too long: {field}")
        for field in LIST_FIELDS:
            value = summary.get(field)
            if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
                raise ValueError(f"invalid list field: {field}")
            if len(value) > 4:
                raise ValueError(f"too many items in {field}")
            if any(len(item) > 500 for item in value):
                raise ValueError(f"list item too long in {field}")
        ids = summary.get("evidence_ids")
        if not isinstance(ids, list) or not ids or any(not re.fullmatch(r"E(?:10|[1-9])", str(x)) for x in ids):
            raise ValueError("invalid evidence_ids")
        narrative = " ".join(str(summary[f]) for f in NARRATIVE_FIELDS)
        narrative += " " + " ".join(x for f in LIST_FIELDS for x in summary[f])
        if INTERNAL_NARRATIVE.search(narrative):
            raise ValueError("AI narrative exposes internal field names or evidence IDs")
        if READER_JARGON.search(narrative):
            raise ValueError("AI narrative exposes unexplained technical or process jargon")
        # Evidence cards render all numbers deterministically.  The AI narrative is
        # forbidden from inventing or rounding its own numeric claims.
        if re.search(r"\d", re.sub(r"E(?:10|[1-9])", "", narrative)):
            raise ValueError("AI narrative contains digits; numeric claims belong in evidence cards")
        if not re.search(r"[\u4e00-\u9fff]", narrative):
            raise ValueError("AI narrative must contain Traditional Chinese")
    return summaries


def legacy_rewrite_periods(history: dict, max_periods: int = 31) -> tuple[list[dict], dict]:
    """Select stored periods whose prose fails today's reader-safety contract."""
    due = []
    backlog = {}
    for scale in SCALES:
        candidates = []
        records = history.get("periods", {}).get(scale, {})
        for record in records.values():
            period = record.get("period")
            summary = record.get("ai")
            if record.get("status") != "AI_GENERATED" or not isinstance(period, dict):
                continue
            try:
                validate_ai_output(
                    json.dumps({"summaries": [summary]}, ensure_ascii=False), [period]
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                candidates.append(period)
        candidates.sort(key=lambda p: p["end"])
        backlog[scale] = max(0, len(candidates) - max_periods)
        due.extend(candidates[:max_periods])
    due.sort(key=lambda p: (p["end"], SCALES.index(p["scale"])))
    return due, backlog


def invoke_ai(evidence_doc: dict, timeout: int, provider: str = "auto",
              claude_model: str = "claude-sonnet-5", max_budget_usd: float = 1.0) -> str:
    template = PROMPT.read_text(encoding="utf-8")
    prompt = template + "\n\n以下是本次唯一可用的 evidence JSON：\n" + json.dumps(evidence_doc, ensure_ascii=False)
    agy = shutil.which("agy") if provider in {"auto", "agy"} else None
    claude = ((shutil.which("claude.cmd") or shutil.which("claude"))
              if provider in {"auto", "claude"} else None)
    if agy:
        command = [agy, f"--print={prompt}", "--mode=accept-edits"]
        input_text = None
    elif claude:
        command = [
            claude, "--print", "--bare", "--tools", "", "--model", claude_model,
            "--effort", "low", "--max-budget-usd", str(max_budget_usd),
            "--no-session-persistence", "--permission-mode", "dontAsk",
        ]
        input_text = prompt
    else:
        raise RuntimeError(f"AI provider not found: {provider}")
    result = subprocess.run(
        command, input=input_text, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-500:]
        raise RuntimeError(f"AI provider failed rc={result.returncode}: {detail}")
    return result.stdout


def _latest_map(history: dict) -> dict:
    out = {}
    for scale in SCALES:
        records = [r for r in history.get("periods", {}).get(scale, {}).values()
                   if r.get("status") == "AI_GENERATED"]
        if records:
            out[scale] = max(records, key=lambda r: r["period"]["end"])
    return out


def persist_results(history: dict, evidence_doc: dict, summaries: list[dict], run_date: str) -> dict:
    by_key = {(s["scale"], s["period_id"]): s for s in summaries}
    history.setdefault("schema_version", 1)
    history.setdefault("initialized_at", datetime.now(timezone.utc).isoformat())
    periods = history.setdefault("periods", {scale: {} for scale in SCALES})
    for evidence in evidence_doc["periods"]:
        period = evidence["period"]
        ai = by_key[(period["scale"], period["period_id"])]
        periods.setdefault(period["scale"], {})[period["period_id"]] = {
            "status": "AI_GENERATED",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_date": run_date,
            "period": period,
            "time_contract": evidence["time_contract"],
            "evidence": evidence["evidence"],
            "ai": ai,
        }
    history["latest"] = _latest_map(history)
    return history


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--model-report", type=Path, default=MODEL_REPORT)
    parser.add_argument("--taxonomy-report", type=Path, default=TAXONOMY_REPORT)
    parser.add_argument("--recommendations", type=Path, default=RECOMMENDATIONS)
    parser.add_argument("--history", type=Path, default=HISTORY_OUT)
    parser.add_argument("--evidence-output", type=Path, default=EVIDENCE_OUT)
    parser.add_argument("--status-output", type=Path, default=STATUS_OUT)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--ai-output", type=Path, help="validated offline/test AI JSON instead of invoking agy")
    parser.add_argument("--ai-provider", choices=("auto", "agy", "claude"), default="auto")
    parser.add_argument("--claude-model", default="claude-sonnet-5")
    parser.add_argument("--max-ai-budget-usd", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-periods", type=int, default=31)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    run_date = date.fromisoformat(args.date)
    rows = load_rows(args.master)
    model_report = load_json(args.model_report, {})
    freshness = master_freshness(rows, model_report, args.master)
    history = load_json(args.history, {"schema_version": 1, "periods": {s: {} for s in SCALES}})
    scheduled_due, scheduled_backlog = due_periods(history, run_date, args.max_periods)
    rewrite_due, rewrite_backlog = legacy_rewrite_periods(history, args.max_periods)
    by_key = {
        (period["scale"], period["period_id"]): period
        for period in scheduled_due + rewrite_due
    }
    due = sorted(by_key.values(), key=lambda p: (p["end"], SCALES.index(p["scale"])))
    backlog = {
        scale: scheduled_backlog.get(scale, 0) + rewrite_backlog.get(scale, 0)
        for scale in SCALES
    }
    plan = {
        "run_date": args.date, "freshness": freshness, "due": due,
        "rewrite_due": rewrite_due, "backlog": backlog,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    if args.plan_only:
        return 0 if freshness["status"] == "CURRENT" else 2
    if freshness["status"] != "CURRENT":
        status = {**plan, "status": "BLOCKED_STALE_CORPUS", "updated_periods": []}
        args.status_output.parent.mkdir(parents=True, exist_ok=True)
        args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("timescale summaries blocked: stale master/model report", flush=True)
        return 2
    if not due:
        status = {**plan, "status": "NO_PERIOD_DUE", "updated_periods": []}
        args.status_output.parent.mkdir(parents=True, exist_ok=True)
        args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return 0

    evidence_doc = {
        "schema_version": 1, "run_date": args.date, "freshness": freshness,
        "periods": [
            build_period_evidence(
                rows, period, freshness, load_json(args.taxonomy_report, {}),
                load_json(args.recommendations, {}),
            ) for period in due
        ],
    }
    args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
    args.evidence_output.write_text(json.dumps(evidence_doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    try:
        raw = (args.ai_output.read_text(encoding="utf-8") if args.ai_output else
               invoke_ai(
                   evidence_doc, args.timeout, args.ai_provider,
                   args.claude_model, args.max_ai_budget_usd,
               ))
        summaries = validate_ai_output(raw, due)
    except Exception as exc:
        status = {**plan, "status": "AI_BLOCKED", "error": str(exc), "updated_periods": []}
        args.status_output.parent.mkdir(parents=True, exist_ok=True)
        args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"timescale summaries AI blocked: {exc}", flush=True)
        return 0  # publish the truthful blocked state and retry next daily run

    history = persist_results(history, evidence_doc, summaries, args.date)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    args.history.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    updated = [{"scale": s["scale"], "period_id": s["period_id"]} for s in summaries]
    status = {**plan, "status": "AI_GENERATED", "updated_periods": updated}
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"timescale summaries updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
