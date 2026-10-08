#!/usr/bin/env python3
"""Fail the watchdog when remote main or live Pages health is stale."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from safe_http import fetch_bytes


ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PROOF_REQUIRED_FROM = "2026-07-29"
# 契約的本意是「這一次是排程觸發的，不是人手動跑的」，不是「一定要 macOS」。
# 2026-10-08 這條 routine 從 Mac 交接給另一台機器，所以改成排程器白名單；
# manual / manual_recovery 照樣擋下。新增一種排程器就在這裡加一個值。
SCHEDULER_CONTEXTS = frozenset({"launchd", "schtasks", "cron", "systemd", "github-actions"})
LAUNCHD_PROOF_REQUIRED_FROM = SCHEDULER_PROOF_REQUIRED_FROM  # 舊名保留，避免外部引用壞掉
PIPELINE_EVIDENCE_REQUIRED_FROM = "2026-07-29"


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
    if expected_date >= PIPELINE_EVIDENCE_REQUIRED_FROM:
        gates = health.get("gates", {})
        if gates.get("corpus_update") != "SUCCESS":
            errors.append(f"corpus_update={gates.get('corpus_update')} expected=SUCCESS")
        if gates.get("security_intake") not in {"PASS", "PASS_WITH_QUARANTINE"}:
            errors.append(f"security_intake={gates.get('security_intake')} is not successful")
        if gates.get("editorial_markdown") != "PASS":
            errors.append(f"editorial_markdown={gates.get('editorial_markdown')} expected=PASS")
        if gates.get("editorial_html") != "PASS":
            errors.append(f"editorial_html={gates.get('editorial_html')} expected=PASS")
        if gates.get("domain_zones") != "PASS":
            errors.append(f"domain_zones={gates.get('domain_zones')} expected=PASS")
    if expected_date >= SCHEDULER_PROOF_REQUIRED_FROM:
        context = health.get("schedule_contract", {}).get("execution_context")
        if context not in SCHEDULER_CONTEXTS:
            expected = "|".join(sorted(SCHEDULER_CONTEXTS))
            errors.append(f"execution_context={context} expected={expected}")
    return errors


def load_remote_health(url, timeout=20):
    """Fetch live Pages with a cache buster; a checked-out file is not publish proof."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("watchdog", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    live_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    payload = fetch_bytes(
        live_url,
        allowed_hosts={"hsintiger.github.io"},
        allowed_content_types={"application/json"},
        max_bytes=256_000,
        timeout=timeout,
        user_agent="skills-radar-freshness-watchdog/1",
        extra_headers={"Cache-Control": "no-cache"},
    )
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
