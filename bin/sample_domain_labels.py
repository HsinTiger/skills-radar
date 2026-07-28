#!/usr/bin/env python3
"""Select bounded new-topic rows for the existing domain LLM classifier.

The normal path selects only rows that have never been labelled.  Recovery may
explicitly include model-labelled rows so a lost LLM batch can be replaced by a
new, auditable golden sample without pretending to reconstruct the old labels.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random

from asic_taxonomy import content_signature
from build_asic_catalog import read_rows


ROOT = Path(__file__).resolve().parents[1]


def select(rows: list[dict], sample_names: set[str], n: int, seed: int,
           include_model: bool = False) -> list[dict]:
    seen: set[str] = set()
    buckets: defaultdict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if sample_names and row.get("sample") not in sample_names:
            continue
        labelled_by_model = row.get("domain") and row.get("label_source") == "model"
        if row.get("domain") and not (include_model and labelled_by_model):
            continue
        signature = content_signature(row)
        if signature in seen:
            continue
        seen.add(signature)
        tiers = row.get("topic_tier") or ["untiered"]
        buckets[f"{row.get('sample')}|{tiers[0]}"].append(row)
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
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--include-model", action="store_true",
        help="recovery only: audit model-labelled rows as a new LLM golden sample",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "corpus" / "domain-golden-sample.jsonl")
    args = parser.parse_args()
    selected = select(
        read_rows(args.master), set(args.sample), args.n, args.seed,
        include_model=args.include_model,
    )
    if not selected:
        raise SystemExit("no unlabelled rows found for requested samples")
    with args.output.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Domain golden sample: {len(selected)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
