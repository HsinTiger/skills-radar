#!/usr/bin/env python3
"""Fail the watchdog when remote main or live Pages health is stale."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
LAUNCHD_PROOF_REQUIRED_FROM = "2026-07-29"


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
    if expected_date >= LAUNCHD_PROOF_REQUIRED_FROM:
        context = health.get("schedule_contract", {}).get("execution_context")
        if context != "launchd":
            errors.append(f"execution_context={context} expected=launchd")
    return errors


def load_remote_health(url, timeout=20):
    """Fetch live Pages with a cache buster; a checked-out file is not publish proof."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("watchdog", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    live_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    request = Request(
        live_url,
        headers={"Cache-Control": "no-cache", "User-Agent": "skills-radar-freshness-watchdog/1"},
    )
    with urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise RuntimeError(f"live health HTTP {status}")
        payload = response.read()
    return json.loads(payload.decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--health", type=Path, default=ROOT / "docs" / "pipeline_health.json")
    parser.add_argument("--health-url", help="live Pages health URL; compared with checked-out artifact")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--date", default=datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat())
    args = parser.parse_args(argv)
    if not args.health.exists():
        print(f"freshness FAIL: health marker missing: {args.health}")
        return 1
    expected = json.loads(args.health.read_text(encoding="utf-8"))
    if args.health_url:
        try:
            health = load_remote_health(args.health_url, args.timeout)
        except Exception as exc:
            print(f"freshness FAIL: live Pages readback failed: {exc}")
            return 1
    else:
        health = expected
    errors = validate_health(health, args.date)
    if args.health_url and health != expected:
        errors.append("live Pages health differs from the checked-out remote main artifact")
    if errors:
        print("freshness FAIL:")
        for error in errors:
            print(f"- {error}")
        return 1
    source = args.health_url or str(args.health)
    print(f"freshness PASS: {args.date}; source={source}; pipeline=PASS; "
          f"master=CURRENT; timescale={health['gates']['timescale_dispatch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
