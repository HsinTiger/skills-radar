#!/usr/bin/env python3
"""Strictly merge one complete LLM classification batch into master.jsonl."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLASSIFIED = ROOT / "corpus" / "classified.jsonl"
DEFAULT_MASTER = ROOT / "corpus" / "master.jsonl"

DOMAINS = {
    "software-dev", "data-analytics", "devops-infra", "security", "hardware-eda",
    "research-academia", "writing-content", "marketing-growth", "design-creative",
    "finance-investing", "legal-compliance", "healthcare-bio", "education-training",
    "sales-crm", "ops-admin", "personal-productivity", "ai-agent-tooling", "other",
}
TASKS = {"generate", "transform", "analyze", "verify", "orchestrate", "retrieve", "configure"}
TARGETS = {"self", "team", "client", "public", "agent"}
MATURITIES = {"toy", "workflow", "production"}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: expected JSON object")
            rows.append(value)
    return rows


def validate_classifications(labels: list[dict], expected_count: int) -> list[str]:
    errors = []
    seen = set()
    for label in labels:
        index = label.get("i")
        if not isinstance(index, int) or isinstance(index, bool):
            errors.append(f"invalid index: {index!r}")
            continue
        if index in seen:
            errors.append(f"duplicate index: {index}")
        seen.add(index)
        if label.get("domain") not in DOMAINS:
            errors.append(f"i={index}: invalid domain")
        if label.get("task") not in TASKS:
            errors.append(f"i={index}: invalid task")
        if label.get("target") not in TARGETS:
            errors.append(f"i={index}: invalid target")
        if label.get("maturity") not in MATURITIES:
            errors.append(f"i={index}: invalid maturity")
        if not isinstance(label.get("profession"), str) or not label["profession"].strip():
            errors.append(f"i={index}: invalid profession")
        if not isinstance(label.get("pain"), str) or not label["pain"].strip():
            errors.append(f"i={index}: invalid pain")
        if not isinstance(label.get("injection_suspect"), bool):
            errors.append(f"i={index}: invalid injection_suspect")
    expected = set(range(expected_count))
    missing = expected - seen
    extra = seen - expected
    if missing:
        errors.append(f"missing indices: {sorted(missing)}")
    if extra:
        errors.append(f"extra indices: {sorted(extra)}")
    return errors


def unique_keys(rows: list[dict], source: str) -> dict[tuple[str, str], int]:
    result = {}
    for index, row in enumerate(rows):
        key = (row.get("repo"), row.get("path"))
        if not all(isinstance(value, str) and value for value in key):
            raise ValueError(f"{source}: row {index} lacks repo/path")
        if key in result:
            raise ValueError(f"{source}: duplicate repo/path {key!r}")
        result[key] = index
    return result


def merge(delta: list[dict], labels: list[dict], master: list[dict]) -> list[dict]:
    errors = validate_classifications(labels, len(delta))
    if errors:
        raise ValueError("classification batch rejected: " + "; ".join(errors))
    unique_keys(delta, "delta")
    master_index = unique_keys(master, "master")
    by_index = {label["i"]: label for label in labels}
    updated = list(master)
    for index, source in enumerate(delta):
        label = by_index[index]
        row = dict(source)
        for field in ("domain", "profession", "task", "target", "maturity", "pain",
                      "injection_suspect"):
            row[field] = label[field]
        row["label_source"] = "llm"
        for field in ("domain_conf", "task_conf", "target_conf", "maturity_conf"):
            row.pop(field, None)
        key = (row["repo"], row["path"])
        if key in master_index:
            updated[master_index[key]] = row
        else:
            master_index[key] = len(updated)
            updated.append(row)
    return updated


def write_jsonl_atomic(path: Path, rows: list[dict]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("delta", type=Path)
    parser.add_argument("--classified", type=Path, default=DEFAULT_CLASSIFIED)
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    args = parser.parse_args(argv)
    delta = read_jsonl(args.delta)
    labels = read_jsonl(args.classified)
    master = read_jsonl(args.master)
    updated = merge(delta, labels, master)
    write_jsonl_atomic(args.master, updated)
    print(f"[merge] merged {len(delta)} complete LLM labels; master rows={len(updated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
