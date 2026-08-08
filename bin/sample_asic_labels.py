#!/usr/bin/env python3
"""Create a deterministic stratified sample for ASIC secondary LLM labels."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random

from asic_taxonomy import classify_row, content_signature, is_hardware_candidate
from build_asic_catalog import read_rows


ROOT = Path(__file__).resolve().parents[1]


def select(rows: list[dict], sample_names: set[str], n: int, seed: int) -> list[dict]:
    seen_signatures: set[str] = set()
    buckets: defaultdict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if sample_names and row.get("sample") not in sample_names:
            continue
        if row.get("asic_label_source") == "llm" or not is_hardware_candidate(row):
            continue
        signature = content_signature(row)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        routed = classify_row(row)
        tiers = row.get("topic_tier") or ["untiered"]
        key = f"{row.get('sample') or 'neutral'}|{tiers[0]}|{routed['hardware_target']}|{routed['owner_fit']}"
        buckets[key].append(row)

    rng = random.Random(seed)
    for values in buckets.values():
        rng.shuffle(values)
    selected: list[dict] = []
    keys = sorted(buckets)
    while keys and len(selected) < n:
        next_keys: list[str] = []
        for key in keys:
            if buckets[key] and len(selected) < n:
                selected.append(buckets[key].pop())
            if buckets[key]:
                next_keys.append(key)
        keys = next_keys
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=ROOT / "corpus" / "master.jsonl")
    parser.add_argument("--sample", action="append", default=["targeted-asic", "targeted-wifi-asic"])
    parser.add_argument("--n", type=int, default=240)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, default=ROOT / "corpus" / "asic-golden-sample.jsonl")
    args = parser.parse_args()

    selected = select(read_rows(args.master), set(args.sample), args.n, args.seed)
    if not selected:
        raise SystemExit("no eligible unlabelled ASIC rows found; run domain labelling/training first")
    with args.output.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"ASIC golden sample: {len(selected)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
