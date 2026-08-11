#!/usr/bin/env python3
"""Quarantine suspicious third-party text before any analysis or model call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scan_injection import scan_text


UNTRUSTED_ROW_FIELDS = (
    "repo", "path", "repo_topics", "name", "description", "body_head",
    "desc_untrusted", "title_untrusted",
    "summary_untrusted", "msg_untrusted", "body_untrusted", "name_untrusted",
)


class UntrustedContentError(ValueError):
    """Untrusted data is malformed or matched a known injection pattern."""


def row_text(row: dict) -> str:
    values = []
    for field in UNTRUSTED_ROW_FIELDS:
        value = row.get(field)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(str(item) for item in value if isinstance(item, (str, int, float)))
    return " ".join(values)


def inspect_text(text: str) -> dict:
    score, hits = scan_text(text or "")
    return {"score": score, "hits": hits}


def assert_text_safe(text: str, *, source: str = "untrusted payload") -> None:
    result = inspect_text(text)
    if result["score"]:
        categories = ", ".join(sorted(result["hits"]))
        raise UntrustedContentError(
            f"{source} rejected by security gate: score={result['score']} categories={categories}"
        )


def partition_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    accepted = []
    quarantined = []
    for row in rows:
        if not isinstance(row, dict):
            raise UntrustedContentError("collector returned a non-object row")
        result = inspect_text(row_text(row))
        if result["score"]:
            quarantined.append({"row": row, **result})
        else:
            accepted.append(row)
    return accepted, quarantined


def verify_jsonl(path: Path) -> int:
    rows = []
    try:
        with Path(path).open(encoding="utf-8", errors="strict") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise UntrustedContentError(f"{path}:{line_no} contains invalid JSON") from exc
                if not isinstance(row, dict):
                    raise UntrustedContentError(f"{path}:{line_no} is not a JSON object")
                rows.append(row)
    except UnicodeError as exc:
        raise UntrustedContentError(f"{path} is not valid UTF-8") from exc
    _accepted, quarantined = partition_rows(rows)
    if quarantined:
        categories = sorted({category for item in quarantined for category in item["hits"]})
        raise UntrustedContentError(
            f"{path} contains {len(quarantined)} suspicious row(s): {', '.join(categories)}"
        )
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        count = verify_jsonl(args.path)
    except (OSError, UntrustedContentError) as exc:
        print(f"security gate BLOCKED: {exc}")
        return 2
    print(f"security gate PASS: {count} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
