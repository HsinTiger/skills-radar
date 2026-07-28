#!/usr/bin/env python3
"""Write a public, source-bounded health marker for the last local daily run."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def nonempty(path):
    return path.exists() and path.stat().st_size > 0


def build_health(report_date, privacy_passed=False, root=ROOT, run_context=None):
    rec = load(root / "corpus" / "daily_skill_recommendations.json", {})
    ts = load(root / "data" / "timescale_summary_status.json", {})
    update = load(root / "data" / "corpus_update_manifest.json", {})
    daily_ok = nonempty(root / "daily" / f"{report_date}.md")
    editorial_md_ok = nonempty(root / "research" / "editorials" / f"{report_date}.md")
    editorial_html_ok = nonempty(root / "docs" / "editorials" / f"{report_date}.html")
    zones = load(root / "corpus" / "domain_zones.json", {})
    zones_ran = (
        zones.get("report_date") == report_date
        and nonempty(root / "docs" / "eda-ic" / "index.html")
        and nonempty(root / "docs" / "investing" / "index.html")
    )
    zones_ok = zones_ran and zones.get("status") == "READY_FOR_OWNER_REVIEW"
    update_current = update.get("run_date") == report_date
    update_ok = update_current and update.get("status") == "SUCCESS"
    rec_ok = rec.get("report_date") == report_date and rec.get("status") == "READY_FOR_OWNER_REVIEW"
    ts_ran = ts.get("run_date") == report_date
    ts_ok = ts_ran and ts.get("status") in {"AI_GENERATED", "NO_PERIOD_DUE"}
    core_ok = update_ok and daily_ok and rec_ok and zones_ran and privacy_passed and ts_ran
    if not core_ok:
        status = "FAIL"
    elif not editorial_md_ok or not editorial_html_ok or not ts_ok or not zones_ok:
        status = "PARTIAL"
    else:
        status = "PASS"
    execution_context = run_context or os.environ.get("SKILLS_RADAR_RUN_CONTEXT", "manual_or_unknown")
    return {
        "schema_version": 1,
        "report_date": report_date,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gates": {
            "corpus_update": update.get("status", "NOT_RUN") if update_current else "NOT_RUN",
            "daily_brief": "PASS" if daily_ok else "FAIL",
            "daily_recommendations": "PASS" if rec_ok else "FAIL",
            "domain_zones": "PASS" if zones_ok else "FAIL",
            "editorial_markdown": "PASS" if editorial_md_ok else "MISSING",
            "editorial_html": "PASS" if editorial_html_ok else "MISSING",
            "legacy_opportunity_insight": "ARCHIVE_ONLY",
            "timescale_dispatch": ts.get("status", "NOT_RUN") if ts_ran else "NOT_RUN",
            "privacy": "PASS" if privacy_passed else "NOT_PROVEN",
            "master_freshness": rec.get("corpus_freshness", {}).get("status", "UNKNOWN"),
        },
        "corpus_update": {
            "status": update.get("status", "NOT_RUN") if update_current else "NOT_RUN",
            "new_rows": update.get("new_rows") if update_current else None,
            "rows_after": (update.get("after") or {}).get("rows") if update_current else None,
            "run_context": update.get("run_context") if update_current else None,
        },
        "timescale": {
            "updated_periods": ts.get("updated_periods", []),
            "due": ts.get("due", []),
            "backlog": ts.get("backlog", {}),
        },
        "schedule_contract": {
            "dispatcher": "daily 08:30 Asia/Taipei",
            "scheduler_source": "bin/launchd_schedule.py is rendered by bin/install_launchd.sh",
            "execution_context": execution_context,
            "day": "previous complete day",
            "week": "previous complete Monday-Sunday week",
            "month": "previous complete calendar month",
            "quarter": "previous complete calendar quarter",
            "catch_up": "missing period_id only",
        },
        "remote_publish": "NOT_PROVEN_UNTIL_REMOTE_READBACK",
        "claim_boundary": "local PASS proves a successful public collector readback plus required local artifacts; it does not prove git push, Pages deployment, skill correctness, EDA signoff, or investment outcome",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--privacy-passed", action="store_true")
    parser.add_argument("--run-context")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "pipeline_health.json")
    parser.add_argument("--public-output", type=Path, default=ROOT / "docs" / "pipeline_health.json")
    args = parser.parse_args(argv)
    health = build_health(args.date, args.privacy_passed, run_context=args.run_context)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(health, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    args.public_output.parent.mkdir(parents=True, exist_ok=True)
    args.public_output.write_text(json.dumps(health, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(health, ensure_ascii=False))
    return 0 if health["status"] in {"PASS", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
