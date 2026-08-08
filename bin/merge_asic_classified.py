#!/usr/bin/env python3
"""Strictly validate LLM ASIC-axis labels and merge them into master.jsonl."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from asic_taxonomy import (
    ASIC_STAGES, DIRECT_STAGES, HARDWARE_TARGETS, OWNER_FITS, WIFI_AREAS,
    is_hardware_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


def validate_label(label: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(label.get("i"), int) or isinstance(label.get("i"), bool):
        errors.append("i must be an integer")
    if label.get("hardware_target") not in HARDWARE_TARGETS:
        errors.append("invalid hardware_target")
    if label.get("owner_fit") not in OWNER_FITS:
        errors.append("invalid owner_fit")
    for field, allowed in (("asic_stages", ASIC_STAGES), ("wifi_areas", WIFI_AREAS)):
        values = label.get(field)
        if not isinstance(values, list):
            errors.append(f"{field} must be a list")
        elif len(values) != len(set(values)) or any(value not in allowed for value in values):
            errors.append(f"invalid or duplicate {field}")
    evidence = label.get("evidence")
    if not isinstance(evidence, list) or len(evidence) > 5 or any(
        not isinstance(value, str) or not value.strip() or len(value) > 100 for value in evidence or []
    ):
        errors.append("evidence must be <=5 non-empty short strings")
    if not isinstance(label.get("injection_suspect"), bool):
        errors.append("injection_suspect must be boolean")
    target, fit = label.get("hardware_target"), label.get("owner_fit")
    if target in {"fpga", "embedded", "board-pcb", "analog-rf"} and fit != "exclude":
        errors.append(f"hardware_target={target} requires owner_fit=exclude")
    if target == "physical" and fit == "direct":
        errors.append("physical target cannot be owner_fit=direct")
    if label.get("wifi_areas") == ["rf"] and fit != "exclude":
        errors.append("RF-only skill requires owner_fit=exclude")
    if fit == "direct" and (
        target != "asic" or not DIRECT_STAGES.intersection(label.get("asic_stages") or [])
    ):
        errors.append("owner_fit=direct requires ASIC target and a direct front-end stage")
    return errors


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("delta", type=Path, help="exact rows sent to the ASIC labelling prompt")
    parser.add_argument("classified", type=Path, help="LLM JSONL output")
    parser.add_argument("--master", type=Path, default=ROOT / "corpus" / "master.jsonl")
    args = parser.parse_args()

    delta = load_jsonl(args.delta)
    labels = load_jsonl(args.classified)
    errors: list[str] = []
    by_index: dict[int, dict] = {}
    for line_no, label in enumerate(labels, 1):
        row_errors = validate_label(label)
        if row_errors:
            errors.append(f"classified line {line_no}: {', '.join(row_errors)}")
            continue
        index = label["i"]
        if index in by_index:
            errors.append(f"duplicate i={index}")
        elif not 0 <= index < len(delta):
            errors.append(f"i={index} outside delta range")
        else:
            by_index[index] = label
    missing = sorted(set(range(len(delta))) - set(by_index))
    if missing:
        errors.append(f"missing labels for {len(missing)} rows; first={missing[:10]}")
    for index, row in enumerate(delta):
        if not is_hardware_candidate(row):
            errors.append(f"delta i={index} did not pass hardware-eda domain gate")
    if errors:
        raise SystemExit("ASIC label merge rejected:\n- " + "\n- ".join(errors))

    updates: dict[tuple[str, str], dict] = {}
    for index, row in enumerate(delta):
        label = by_index[index]
        updates[(row.get("repo"), row.get("path"))] = {
            "hardware_target": label["hardware_target"],
            "asic_stages": label["asic_stages"],
            "wifi_areas": label["wifi_areas"],
            "owner_fit": label["owner_fit"],
            "asic_label_evidence": label["evidence"],
            "asic_label_source": "llm",
            "injection_suspect": bool(row.get("injection_suspect")) or label["injection_suspect"],
        }

    master_rows = load_jsonl(args.master)
    found: set[tuple[str, str]] = set()
    for row in master_rows:
        key = (row.get("repo"), row.get("path"))
        if key in updates:
            row.update(updates[key])
            found.add(key)
    absent = set(updates) - found
    if absent:
        raise SystemExit(f"ASIC label merge rejected: {len(absent)} delta rows absent from master")

    temporary = args.master.with_suffix(args.master.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as fh:
        for row in master_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(args.master)
    print(f"[asic-merge] merged {len(updates)} strict LLM labels into {args.master}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
