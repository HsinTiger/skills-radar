#!/usr/bin/env python3
"""Evaluate deterministic ASIC/WiFi routing against strict LLM golden labels."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from asic_taxonomy import classify_row
from build_asic_catalog import read_rows


ROOT = Path(__file__).resolve().parents[1]
GOLD_FIELDS = {
    "asic_label_source", "hardware_target", "asic_stages", "wifi_areas",
    "owner_fit", "asic_label_evidence",
}


def without_gold(row: dict) -> dict:
    return {key: value for key, value in row.items() if key not in GOLD_FIELDS}


def scalar_metrics(pairs: list[tuple[str, str]]) -> dict:
    confusion: defaultdict[str, Counter] = defaultdict(Counter)
    for truth, prediction in pairs:
        confusion[truth][prediction] += 1
    return {
        "accuracy": round(sum(a == b for a, b in pairs) / len(pairs), 3) if pairs else None,
        "confusion": {truth: dict(counts) for truth, counts in sorted(confusion.items())},
    }


def multilabel_metrics(pairs: list[tuple[list[str], list[str]]]) -> dict:
    labels = sorted({label for truth, pred in pairs for label in [*truth, *pred]})
    exact = 0
    jaccards: list[float] = []
    per_label = {}
    for truth, pred in pairs:
        a, b = set(truth), set(pred)
        exact += a == b
        union = a | b
        jaccards.append(len(a & b) / len(union) if union else 1.0)
    for label in labels:
        tp = fp = fn = tn = 0
        for truth, pred in pairs:
            actual, guessed = label in truth, label in pred
            tp += actual and guessed
            fp += not actual and guessed
            fn += actual and not guessed
            tn += not actual and not guessed
        per_label[label] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn}
    return {
        "exact_match": round(exact / len(pairs), 3) if pairs else None,
        "mean_jaccard": round(sum(jaccards) / len(jaccards), 3) if jaccards else None,
        "per_label": per_label,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=ROOT / "corpus" / "master.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "corpus" / "asic_taxonomy_report.json")
    parser.add_argument("--min-n", type=int, default=200)
    parser.add_argument("--min-scalar-accuracy", type=float, default=0.75)
    parser.add_argument("--min-jaccard", type=float, default=0.65)
    args = parser.parse_args()

    golden = [row for row in read_rows(args.master) if row.get("asic_label_source") == "llm"]
    scalar = {"hardware_target": [], "owner_fit": []}
    multi = {"asic_stages": [], "wifi_areas": []}
    for row in golden:
        truth = classify_row(row)
        predicted = classify_row(without_gold(row))
        for field in scalar:
            scalar[field].append((truth[field], predicted[field]))
        for field in multi:
            multi[field].append((truth[field], predicted[field]))

    metrics = {
        **{field: scalar_metrics(pairs) for field, pairs in scalar.items()},
        **{field: multilabel_metrics(pairs) for field, pairs in multi.items()},
    }
    failures: list[str] = []
    if len(golden) < args.min_n:
        failures.append(f"n_golden={len(golden)} < {args.min_n}")
    for field in scalar:
        if metrics[field]["accuracy"] is None or metrics[field]["accuracy"] < args.min_scalar_accuracy:
            failures.append(f"{field}.accuracy below {args.min_scalar_accuracy}")
    for field in multi:
        if metrics[field]["mean_jaccard"] is None or metrics[field]["mean_jaccard"] < args.min_jaccard:
            failures.append(f"{field}.mean_jaccard below {args.min_jaccard}")
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_golden": len(golden),
        "status": "PASS" if not failures else "BLOCKED",
        "thresholds": {
            "min_n": args.min_n,
            "min_scalar_accuracy": args.min_scalar_accuracy,
            "min_jaccard": args.min_jaccard,
        },
        "failures": failures,
        "metrics": metrics,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ASIC taxonomy evaluation: n={len(golden)} status={report['status']}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
