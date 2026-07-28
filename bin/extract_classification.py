#!/usr/bin/env python3
"""Extract classification objects from JSONL or a JSON array without accepting prose."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def extract(text: str) -> list[dict]:
    stripped = re.sub(r"^```(?:json|jsonl)?\s*", "", text.strip(), flags=re.I)
    stripped = re.sub(r"\s*```$", "", stripped)
    try:
        doc = json.loads(stripped)
    except json.JSONDecodeError:
        doc = None
    if isinstance(doc, list) and all(isinstance(item, dict) for item in doc):
        return doc
    if isinstance(doc, dict):
        for key in ("results", "classifications", "items"):
            value = doc.get(key)
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                return value

    rows = []
    for line in stripped.splitlines():
        candidate = line.strip().rstrip(",")
        if not candidate.startswith("{"):
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    if not rows:
        raise ValueError("provider output contains no parseable classification objects")
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    rows = extract(args.input.read_text(encoding="utf-8", errors="replace"))
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        temporary.replace(args.output)
    finally:
        if temporary.exists():
            temporary.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
