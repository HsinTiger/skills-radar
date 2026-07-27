#!/usr/bin/env python3
"""Build a WiFi ASIC / RTL candidate catalog from an eligible corpus snapshot.

Default behaviour fails closed when ``master.jsonl`` is older than the tracked
model report.  ``--allow-stale-snapshot`` is an explicit research-only escape
hatch; its output is marked PROVISIONAL/BLOCKED and must not be used for trend
or population claims.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from asic_taxonomy import classify_row, content_signature, is_hardware_candidate


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MASTER = ROOT / "corpus" / "master.jsonl"
DEFAULT_REPORT = ROOT / "corpus" / "model_report.json"
DEFAULT_OUTPUT = ROOT / "corpus" / "asic_skill_catalog.json"
DEFAULT_TAXONOMY_REPORT = ROOT / "corpus" / "asic_taxonomy_report.json"


def read_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def alignment(rows: list[dict], report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    actual_seed = sum(
        bool(row.get("domain")) and row.get("label_source") != "model" for row in rows
    )
    actual_model = sum(row.get("label_source") == "model" for row in rows)
    expected_seed = report.get("n_seed")
    expected_model = report.get("n_predicted")
    return {
        "status": "CURRENT" if (actual_seed, actual_model) == (expected_seed, expected_model) else "STALE",
        "actual_seed": actual_seed,
        "actual_model": actual_model,
        "expected_seed": expected_seed,
        "expected_model": expected_model,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def representative(group: list[dict]) -> dict:
    fit_order = {"direct": 3, "supporting": 2, "adjacent": 1, "exclude": 0}
    return max(
        group,
        key=lambda item: (
            fit_order[item["taxonomy"]["owner_fit"]],
            item["taxonomy"]["fit_score"],
            item["row"].get("stars") or 0,
        ),
    )


def counter_for(candidates: list[dict], key: str) -> dict[str, int]:
    return dict(Counter(candidate[key] for candidate in candidates).most_common())


def list_counter(candidates: list[dict], key: str) -> dict[str, int]:
    values = Counter()
    for candidate in candidates:
        values.update(candidate[key])
    return dict(values.most_common())


def build(rows: list[dict], master: Path, model_alignment: dict, provisional: bool) -> dict:
    classified: list[dict] = []
    for row in rows:
        if not is_hardware_candidate(row):
            continue
        classified.append({"row": row, "taxonomy": classify_row(row)})

    groups: defaultdict[str, list[dict]] = defaultdict(list)
    for item in classified:
        groups[content_signature(item["row"])].append(item)

    candidates: list[dict] = []
    for signature, group in groups.items():
        picked = representative(group)
        row, taxonomy = picked["row"], picked["taxonomy"]
        sources = sorted(
            {
                f"{item['row'].get('repo')}/{item['row'].get('path')}"
                for item in group
            }
        )
        # Full regex hits are reproducible from the pinned taxonomy code and raw
        # snapshot. Keep the tracked signal table bounded; detailed evidence is
        # persisted only for manually reviewed finalists.
        compact_taxonomy = {
            key: value for key, value in taxonomy.items()
            if key not in {"target_evidence", "stage_evidence", "wifi_evidence"}
        }
        candidate = {
            "id": f"{row.get('repo')}:{row.get('path')}",
            "repo": row.get("repo"),
            "path": row.get("path"),
            "name": row.get("name"),
            "stars": row.get("stars") or 0,
            "sample": row.get("sample") or "neutral",
            "label_source": row.get("label_source") or "legacy-llm",
            "domain_conf": row.get("domain_conf"),
            "injection_suspect": bool(row.get("injection_suspect")),
            "content_signature": signature,
            "duplicate_count": len(sources),
            "duplicate_sources": sources[:8],
            "source_pin_status": "UNPINNED",
            **compact_taxonomy,
        }
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            {"A": 3, "B": 2, "C": 1, "D": 0}[item["provisional_grade"]],
            item["fit_score"],
            item["stars"],
        ),
        reverse=True,
    )

    taxonomy_validation = {"status": "MISSING", "n_golden": 0}
    if DEFAULT_TAXONOMY_REPORT.exists():
        report = json.loads(DEFAULT_TAXONOMY_REPORT.read_text(encoding="utf-8"))
        taxonomy_validation = {
            "status": report.get("status"),
            "n_golden": report.get("n_golden"),
            "failures": report.get("failures") or [],
        }
    validation_blocked = taxonomy_validation.get("status") != "PASS"
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PROVISIONAL_STALE_SNAPSHOT" if provisional else "CURRENT_CANDIDATE_CATALOG",
        "canonical_use": "BLOCKED" if provisional or validation_blocked else "CANDIDATE_ROUTING_ONLY",
        "snapshot": {
            "path": str(master.relative_to(ROOT)) if master.is_relative_to(ROOT) else str(master),
            "sha256": sha256_file(master),
            "n_rows": len(rows),
            "model_alignment": model_alignment,
            "taxonomy_validation": taxonomy_validation,
        },
        "methodology": {
            "domain_gate": "domain=hardware-eda and field-specific confidence >=0.6 for model labels",
            "secondary_split": "deterministic regex only after domain gate",
            "population_claims_allowed": False,
            "asic_signoff_evidence": False,
            "next_gate": "LLM-label a new-distribution sample, validate FPGA false positives, then retrain",
        },
        "summary_counts": {
            "eligible_hardware_rows": len(classified),
            "deduplicated_candidates": len(candidates),
            "owner_fit": counter_for(candidates, "owner_fit"),
            "provisional_grade": counter_for(candidates, "provisional_grade"),
            "hardware_target": counter_for(candidates, "hardware_target"),
            "asic_stages": list_counter(candidates, "asic_stages"),
            "wifi_areas": list_counter(candidates, "wifi_areas"),
        },
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--model-report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-stale-snapshot", action="store_true")
    args = parser.parse_args()

    rows = read_rows(args.master)
    model_alignment = alignment(rows, args.model_report)
    stale = model_alignment["status"] != "CURRENT"
    if stale and not args.allow_stale_snapshot:
        raise SystemExit(
            "BLOCKED: master/model_report mismatch; refresh canonical master or pass "
            "--allow-stale-snapshot for explicitly provisional candidate research"
        )
    result = build(rows, args.master, model_alignment, provisional=stale)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts = result["summary_counts"]
    print(
        f"ASIC catalog: {counts['eligible_hardware_rows']} eligible rows -> "
        f"{counts['deduplicated_candidates']} deduplicated candidates; status={result['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
