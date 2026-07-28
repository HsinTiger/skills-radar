#!/usr/bin/env python3
"""Build a small, source-bounded evidence pack for the daily editorial."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCALES = ("day", "week", "month", "quarter")
SCALE_LABELS = {
    "day": "日觀察", "week": "週觀察", "month": "月觀察", "quarter": "季觀察",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compact_period(record: dict) -> dict:
    evidence = record.get("evidence", {})
    return {
        "status": record.get("status"),
        "period": record.get("period"),
        "ai_summary": record.get("ai"),
        "deterministic_evidence": {
            key: evidence.get(key)
            for key in (
                "E1_sample", "E3_domain_shifts", "E5_task_shifts", "E6_maturity",
                "E8_eda_ic", "E9_finance", "E10_quality",
            )
        },
    }


def safe_recommendation(item: dict) -> dict:
    return {
        key: item.get(key)
        for key in (
            "name", "repo", "recommendation", "owner_fit", "score", "summary",
            "use_in_next_rtl_design", "risks", "evidence_freshness",
        )
        if item.get(key) is not None
    }


def build(run_date: str, root: Path = ROOT) -> dict:
    update = load(root / "data/corpus_update_manifest.json")
    if update.get("run_date") != run_date or update.get("status") != "SUCCESS":
        raise ValueError("current successful corpus update manifest is required")

    rec = load(root / "corpus/daily_skill_recommendations.json")
    if rec.get("report_date") != run_date or rec.get("status") != "READY_FOR_OWNER_REVIEW":
        raise ValueError("current owner-review recommendation report is required")
    if rec.get("corpus_freshness", {}).get("status") != "CURRENT":
        raise ValueError("recommendations must use a CURRENT canonical corpus")

    history = load(root / "data/timescale_summaries.json")
    ts_status = load(root / "data/timescale_summary_status.json")
    if ts_status.get("run_date") != run_date:
        raise ValueError("timescale dispatcher did not run for the editorial date")
    if ts_status.get("status") not in {"AI_GENERATED", "NO_PERIOD_DUE"}:
        raise ValueError("timescale summaries are not in a publishable state")

    opportunity = load(root / "corpus/opportunity.json")
    latest = history.get("latest", {})
    ledger = {
        "C1": {
            "label": "daily corpus update",
            "run_date": update["run_date"],
            "status": update["status"],
            "collector": update["collector"],
            "daily_baseline": update.get("daily_baseline", update["before"]),
            "after": update["after"],
            "daily_new_rows": update["new_rows"],
            "delta_rows": update["delta_rows"],
            "run_context": update["run_context"],
            "claim_boundary": update["claim_boundary"],
            "reader_rule": (
                "daily_new_rows is authoritative for what the database gained on the editorial date"
            ),
        },
        **{
            f"T-{scale}": compact_period(latest[scale])
            for scale in SCALES if scale in latest
        },
        "R-EDA": {
            "label": rec["categories"]["EDA_IC"].get("label"),
            "summary": rec["categories"]["EDA_IC"].get("summary"),
            "scope": rec["categories"]["EDA_IC"].get("scope"),
            "excluded_scope": rec["categories"]["EDA_IC"].get("excluded_scope"),
            "recommendations": [
                safe_recommendation(item)
                for item in rec["categories"]["EDA_IC"].get("recommendations", [])[:8]
            ],
        },
        "R-FIN": {
            "label": rec["categories"]["finance-investing"].get("label"),
            "summary": rec["categories"]["finance-investing"].get("summary"),
            "scope": rec["categories"]["finance-investing"].get("scope"),
            "excluded_scope": rec["categories"]["finance-investing"].get("excluded_scope"),
            "recommendations": [
                safe_recommendation(item)
                for item in rec["categories"]["finance-investing"].get("recommendations", [])[:8]
            ],
        },
        "Q": {
            "label": "neutral-corpus opportunity signals",
            "n_total": opportunity.get("n_total"),
            "eligibility": opportunity.get("eligibility"),
            "production_document_proxy_pct": opportunity.get("global_production_pct"),
            "task_mix_pct": opportunity.get("global_task_pct"),
            "top_structural_gaps": opportunity.get("B1_task_gaps", [])[:8],
            "lowest_completion": opportunity.get("B2_unfinished", [])[:6],
            "claim_boundary": "public document labels are proxies, not actual installation, deployment, or outcomes",
        },
    }
    digest = hashlib.sha256(
        json.dumps(ledger, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    citation_labels = {
        "今日採集": "C1",
        **{SCALE_LABELS[scale]: f"T-{scale}" for scale in SCALES if f"T-{scale}" in ledger},
        "EDA 清單": "R-EDA",
        "財經清單": "R-FIN",
        "資料限制": "Q",
    }
    return {
        "schema_version": 1,
        "editorial_date": run_date,
        "status": "READY_FOR_AI_EDITORIAL",
        "evidence_digest": digest,
        "allowed_citations": list(ledger),
        "citation_labels": citation_labels,
        "evidence_ledger": ledger,
        "editorial_contract": {
            "language": "Traditional Chinese (Taiwan)",
            "style": "opinionated evidence-led blog article, not a dashboard dump",
            "required_views": ["thesis", "corpus update", "four timescales", "EDA_IC", "finance", "contrarian", "falsifiers"],
            "numeric_rule": "every Arabic-number claim must already exist in this evidence JSON",
            "confidentiality": "public evidence only; never infer or include employer or internal IC details",
        },
    }


def write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "corpus/editorial_evidence.json")
    args = parser.parse_args(argv)
    evidence = build(args.date)
    write_atomic(args.output, evidence)
    print(f"editorial evidence: {args.date}; digest={evidence['evidence_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
