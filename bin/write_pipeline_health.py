#!/usr/bin/env python3
"""Write a public, source-bounded health marker for the last local daily run."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty(path):
    return path.exists() and path.stat().st_size > 0


def build_health(report_date, privacy_passed=False, root=ROOT):
    rec = load(root / "corpus" / "daily_skill_recommendations.json", {})
    ts = load(root / "data" / "timescale_summary_status.json", {})
    daily_ok = nonempty(root / "daily" / f"{report_date}.md")
    insight_ok = nonempty(root / "research" / "insights" / f"{report_date}.md")
    rec_ok = rec.get("report_date") == report_date and rec.get("status") == "READY_FOR_OWNER_REVIEW"
    ts_ran = ts.get("run_date") == report_date
    ts_ok = ts_ran and ts.get("status") in {"AI_GENERATED", "NO_PERIOD_DUE"}
    core_ok = daily_ok and rec_ok and privacy_passed and ts_ran
    if not core_ok:
        status = "FAIL"
    elif not insight_ok or not ts_ok:
        status = "PARTIAL"
    else:
        status = "PASS"
    return {
        "schema_version": 1,
        "report_date": report_date,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gates": {
            "daily_brief": "PASS" if daily_ok else "FAIL",
            "daily_recommendations": "PASS" if rec_ok else "FAIL",
            "legacy_opportunity_insight": "PASS" if insight_ok else "PARTIAL",
            "timescale_dispatch": ts.get("status", "NOT_RUN") if ts_ran else "NOT_RUN",
            "privacy": "PASS" if privacy_passed else "NOT_PROVEN",
            "master_freshness": rec.get("corpus_freshness", {}).get("status", "UNKNOWN"),
        },
        "timescale": {
            "updated_periods": ts.get("updated_periods", []),
            "due": ts.get("due", []),
            "backlog": ts.get("backlog", {}),
        },
        "schedule_contract": {
            "dispatcher": "daily 08:30 Asia/Taipei",
            "day": "previous complete day",
            "week": "previous complete Monday-Sunday week",
            "month": "previous complete calendar month",
            "quarter": "previous complete calendar quarter",
            "catch_up": "missing period_id only",
        },
        "remote_publish": "NOT_PROVEN_UNTIL_REMOTE_READBACK",
        "claim_boundary": "local PASS does not prove git push, Pages deployment, skill correctness, EDA signoff, or investment outcome",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--privacy-passed", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "pipeline_health.json")
    parser.add_argument("--public-output", type=Path, default=ROOT / "docs" / "pipeline_health.json")
    args = parser.parse_args(argv)
    health = build_health(args.date, args.privacy_passed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(health, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    args.public_output.write_text(json.dumps(health, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(health, ensure_ascii=False))
    return 0 if health["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
