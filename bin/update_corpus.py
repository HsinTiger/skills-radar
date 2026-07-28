#!/usr/bin/env python3
"""Run the daily corpus collector and persist truthful update evidence.

The old shell pipeline treated a crashing collector as "zero new skills".  This
wrapper makes collection failure, a valid zero-delta run, and a real database
change three distinct states.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def inspect_master(path: Path, run_date: str) -> dict:
    digest = hashlib.sha256()
    rows = 0
    first_seen_today = 0
    with path.open("rb") as handle:
        for raw in handle:
            digest.update(raw)
            if not raw.strip():
                continue
            rows += 1
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"master contains invalid JSON at row {rows}") from exc
            if str(record.get("first_seen") or "")[:10] == run_date:
                first_seen_today += 1
    return {
        "rows": rows,
        "sha256": digest.hexdigest(),
        "first_seen_on_run_date": first_seen_today,
    }


def write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _delta_rows(stdout: str, root: Path, run_date: str) -> tuple[str | None, int | None, bool]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        existing = (root / "corpus" / f"delta-{run_date}.jsonl").resolve()
        if not existing.is_file():
            return None, 0, False
        candidate = existing
        reused = True
    else:
        candidate = Path(lines[-1]).resolve()
        reused = False
    corpus_root = (root / "corpus").resolve()
    try:
        candidate.relative_to(corpus_root)
    except ValueError as exc:
        raise ValueError("collector returned a path outside corpus/") from exc
    if not candidate.is_file():
        raise ValueError("collector returned a missing delta file")
    with candidate.open("rb") as handle:
        count = sum(1 for line in handle if line.strip())
    return candidate.name, count, reused


def _validate_delta_in_master(delta_path: Path, master_path: Path) -> bool:
    def keyed(path: Path) -> dict[tuple[str, str], dict]:
        result = {}
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                key = (row.get("repo"), row.get("path"))
                if not all(isinstance(value, str) and value for value in key):
                    raise ValueError(f"{path.name}:{line_no} lacks repo/path")
                if key in result:
                    raise ValueError(f"{path.name} contains duplicate repo/path")
                result[key] = row
        return result
    delta_rows = keyed(delta_path)
    master_rows = keyed(master_path)
    missing = set(delta_rows) - set(master_rows)
    if missing:
        raise ValueError(f"delta contains {len(missing)} rows absent from master")
    required = ("domain", "task", "target", "maturity", "profession", "pain")
    return all(all(master_rows[key].get(field) for field in required) for key in delta_rows)


def _captured_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def run_update(
    run_date: str,
    root: Path = ROOT,
    command: list[str] | None = None,
    timeout_seconds: int = 2400,
) -> tuple[int, dict, str]:
    master = root / "corpus" / "master.jsonl"
    manifest_path = root / "data" / "corpus_update_manifest.json"
    before = inspect_master(master, run_date)
    started_at = datetime.now(timezone.utc).isoformat()
    command = command or [sys.executable, str(root / "bin" / "harvest_delta.py")]
    collector_error = None
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        collector_error = f"collector timed out after {timeout_seconds} seconds"
        result = subprocess.CompletedProcess(
            command, 124, _captured_text(exc.stdout), _captured_text(exc.stderr),
        )
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    status = "FAILED"
    delta_file = None
    delta_rows = None
    reused_daily_delta = False
    delta_already_classified = False
    validation_error = collector_error
    try:
        after = inspect_master(master, run_date)
        delta_file, delta_rows, reused_daily_delta = _delta_rows(result.stdout, root, run_date)
        run_new_rows = after["rows"] - before["rows"]
        if run_new_rows < 0:
            raise ValueError("master row count decreased during an append-only update")
        if reused_daily_delta:
            if run_new_rows != 0:
                raise ValueError("collector changed master but returned no delta path")
            delta_already_classified = _validate_delta_in_master(root / "corpus" / delta_file, master)
        elif delta_rows != run_new_rows:
            raise ValueError(f"delta/master mismatch: delta={delta_rows} master_growth={run_new_rows}")
        if result.returncode == 0 and collector_error is None:
            status = "SUCCESS"
    except Exception as exc:
        after = inspect_master(master, run_date)
        run_new_rows = after["rows"] - before["rows"]
        validation_error = "; ".join(filter(None, (collector_error, str(exc))))

    new_rows = delta_rows if status == "SUCCESS" else max(0, run_new_rows)

    manifest = {
        "schema_version": 1,
        "run_date": run_date,
        "status": status,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "collector": "github_code_search_incremental",
        "collector_exit_code": result.returncode,
        "run_context": os.environ.get("SKILLS_RADAR_RUN_CONTEXT", "manual_or_unknown"),
        "before": before,
        "after": after,
        "new_rows": new_rows,
        "run_new_rows": run_new_rows,
        "delta_file": delta_file,
        "delta_rows": delta_rows,
        "reused_daily_delta": reused_daily_delta,
        "delta_already_classified": delta_already_classified,
        "validation_error": validation_error,
        "claim_boundary": (
            "SUCCESS proves the public collector completed and the local append-only corpus was read back; "
            "new_rows is the preserved run-date delta while run_new_rows is this invocation's growth; "
            "zero new rows is valid, while FAILED must never be reported as zero new rows"
        ),
    }
    write_atomic(manifest_path, manifest)
    if status != "SUCCESS":
        return result.returncode or 2, manifest, ""
    needs_classification = bool(delta_file) and not delta_already_classified
    output_path = str(root / "corpus" / delta_file) if needs_classification else ""
    return 0, manifest, output_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    args = parser.parse_args(argv)
    rc, manifest, delta = run_update(args.date, args.root, timeout_seconds=args.timeout_seconds)
    if rc:
        print(
            f"corpus update FAILED: collector_rc={manifest['collector_exit_code']} "
            f"validation={manifest['validation_error']}",
            file=sys.stderr,
        )
        return rc
    if delta:
        print(delta)
    print(
        f"[corpus-update] SUCCESS rows={manifest['after']['rows']} new={manifest['new_rows']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
