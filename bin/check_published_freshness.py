#!/usr/bin/env python3
"""Fail a remote watchdog when the published daily health marker is stale."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


def validate_health(health, expected_date):
    errors = []
    if health.get("report_date") != expected_date:
        errors.append(f"report_date={health.get('report_date')} expected={expected_date}")
    if health.get("status") != "PASS":
        errors.append(f"status={health.get('status')} expected=PASS")
    freshness = health.get("gates", {}).get("master_freshness")
    if freshness != "CURRENT":
        errors.append(f"master_freshness={freshness} expected=CURRENT")
    timescale = health.get("gates", {}).get("timescale_dispatch")
    if timescale not in {"AI_GENERATED", "NO_PERIOD_DUE"}:
        errors.append(f"timescale_dispatch={timescale} is not successful")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", type=Path, default=ROOT / "docs" / "pipeline_health.json")
    parser.add_argument("--date", default=datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat())
    args = parser.parse_args(argv)
    if not args.health.exists():
        print(f"freshness FAIL: health marker missing: {args.health}")
        return 1
    health = json.loads(args.health.read_text(encoding="utf-8"))
    errors = validate_health(health, args.date)
    if errors:
        print("freshness FAIL:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"freshness PASS: {args.date}; pipeline=PASS; master=CURRENT; timescale={health['gates']['timescale_dispatch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
