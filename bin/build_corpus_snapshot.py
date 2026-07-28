#!/usr/bin/env python3
"""Validate, gzip and manifest the canonical corpus for Release publishing."""

from __future__ import annotations

import argparse
from datetime import date
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def read_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no}: expected object")
            rows.append(row)
    return rows


def validate(rows: list[dict], report: dict) -> dict:
    keys = []
    for index, row in enumerate(rows):
        key = (row.get("repo"), row.get("path"))
        if not all(isinstance(value, str) and value for value in key):
            raise ValueError(f"master row {index} lacks repo/path")
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise ValueError("master contains duplicate repo/path")
    seed = sum(bool(row.get("domain")) and row.get("label_source") != "model" for row in rows)
    model = sum(row.get("label_source") == "model" for row in rows)
    expected_seed = report.get("n_seed")
    expected_model = report.get("n_predicted")
    if (seed, model) != (expected_seed, expected_model):
        raise ValueError(
            f"master/model_report mismatch: actual={seed}/{model} "
            f"expected={expected_seed}/{expected_model}"
        )
    if seed + model != len(rows):
        raise ValueError(f"unclassified rows remain: rows={len(rows)} seed={seed} model={model}")
    return {"rows": len(rows), "unique_keys": len(keys), "seed": seed, "model": model}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def gzip_deterministic(source: Path, output: Path) -> None:
    temporary = output.with_name(output.name + ".tmp")
    try:
        with source.open("rb") as src, temporary.open("wb") as raw:
            with gzip.GzipFile(filename="master.jsonl", mode="wb", fileobj=raw,
                               compresslevel=9, mtime=0) as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def build(master: Path, report_path: Path, gzip_output: Path,
          release_tag: str, snapshot_date: str) -> dict:
    rows = read_rows(master)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    counts = validate(rows, report)
    gzip_output.parent.mkdir(parents=True, exist_ok=True)
    gzip_deterministic(master, gzip_output)
    return {
        "schema_version": 1,
        "snapshot_date": snapshot_date,
        "canonical_status": "CURRENT",
        "release_tag": release_tag,
        "asset_name": gzip_output.name,
        "counts": counts,
        "master_sha256": sha256(master),
        "gzip_sha256": sha256(gzip_output),
        "gzip_bytes": gzip_output.stat().st_size,
        "claim_boundary": "Release digest proves corpus bytes, not skill correctness or EDA runtime proof",
    }


def write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master", type=Path, default=ROOT / "corpus" / "master.jsonl")
    parser.add_argument("--model-report", type=Path, default=ROOT / "corpus" / "model_report.json")
    parser.add_argument("--gzip-output", type=Path, default=ROOT / "corpus" / "master.jsonl.gz")
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "data" / "corpus_snapshot_manifest.json")
    parser.add_argument("--release-tag", default="corpus-latest")
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)
    manifest = build(
        args.master, args.model_report, args.gzip_output,
        args.release_tag, args.date,
    )
    write_json_atomic(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
