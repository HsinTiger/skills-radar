#!/usr/bin/env python3
"""Classify a bounded domain sample with Claude CLI and strict checkpoints.

This is a recovery path for a lost LLM label batch.  It never edits
``master.jsonl``.  Every batch is written below an ignored checkpoint
directory, validated against the requested indices, and only then combined
into ``corpus/classified.jsonl`` for the existing strict merge step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "index" / "prompt_classify.txt"

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
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def parse_output(raw: str) -> list[dict]:
    labels = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            labels.append(value)
    return labels


def validate_labels(labels: list[dict], expected: set[int]) -> list[str]:
    errors = []
    seen = set()
    for label in labels:
        index = label.get("i")
        if not isinstance(index, int) or index not in expected:
            errors.append(f"unexpected index: {index!r}")
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
    missing = expected - seen
    extra = seen - expected
    if missing:
        errors.append(f"missing indices: {sorted(missing)}")
    if extra:
        errors.append(f"extra indices: {sorted(extra)}")
    return errors


def compact_rows(rows: list[dict], start: int) -> list[dict]:
    out = []
    for offset, row in enumerate(rows):
        out.append({
            "i": start + offset,
            "name": str(row.get("name") or "")[:120],
            "description": str(row.get("description") or "")[:400],
            "body_head": str(row.get("body_head") or "")[:450],
            "repo_topics": list(row.get("repo_topics") or [])[:6],
        })
    return out


def run_claude(executable: str, prompt: str, model: str, budget: float, timeout: int) -> str:
    command = [
        executable, "--print", "--bare", "--tools", "", "--model", model,
        "--effort", "low", "--max-budget-usd", str(budget),
        "--no-session-persistence", "--permission-mode", "dontAsk",
    ]
    result = subprocess.run(
        command, input=prompt, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-500:]
        raise RuntimeError(f"claude rc={result.returncode}: {detail}")
    return result.stdout


def classify_batch(rows: list[dict], start: int, executable: str, model: str,
                   budget: float, timeout: int, retries: int) -> list[dict]:
    compact = compact_rows(rows, start)
    expected = {row["i"] for row in compact}
    base = PROMPT.read_text(encoding="utf-8")
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in compact)
    prompt = base + payload + "\n"
    last_errors = []
    provider_error = None
    for attempt in range(1, retries + 1):
        try:
            raw = run_claude(executable, prompt, model, budget, timeout)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            provider_error = exc
            print(f"batch {start}: provider attempt {attempt} failed: {exc}", file=sys.stderr)
            if "Usage Policy" in str(exc) or "Exceeded USD budget" in str(exc):
                break
            continue
        labels = parse_output(raw)
        last_errors = validate_labels(labels, expected)
        if not last_errors:
            return sorted(labels, key=lambda row: row["i"])
        print(f"batch {start}: attempt {attempt} rejected: {last_errors}", file=sys.stderr)
    # One unsafe or unusually long row must not discard the other valid rows.
    # Bisect provider/format failures until the exact blocked index is known;
    # a single blocked row still fails closed and requires an explicit LLM label.
    if len(rows) > 1:
        middle = len(rows) // 2
        return (
            classify_batch(rows[:middle], start, executable, model, budget, timeout, retries)
            + classify_batch(rows[middle:], start + middle, executable, model, budget, timeout, retries)
        )
    detail = provider_error or last_errors
    raise RuntimeError(f"single row i={start} blocked: {detail}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "corpus" / "classified.jsonl")
    parser.add_argument("--checkpoint-dir", type=Path,
                        default=ROOT / "corpus" / ".classified-recovery")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--max-budget-usd", type=float, default=0.25,
                        help="per Claude invocation")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(argv)
    if args.batch_size < 1 or args.batch_size > 40:
        raise SystemExit("batch-size must be between 1 and 40")
    executable = shutil.which("claude.cmd") or shutil.which("claude")
    if not executable:
        raise SystemExit("claude CLI not found")
    rows = read_jsonl(args.corpus)
    if not rows:
        raise SystemExit("empty corpus")
    args.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    all_labels = []
    for start in range(0, len(rows), args.batch_size):
        chunk = rows[start:start + args.batch_size]
        checkpoint = args.checkpoint_dir / f"b{start // args.batch_size:04d}.jsonl"
        expected = set(range(start, start + len(chunk)))
        if checkpoint.exists():
            labels = read_jsonl(checkpoint)
            errors = validate_labels(labels, expected)
            if errors:
                raise SystemExit(f"invalid existing checkpoint {checkpoint}: {errors}")
            print(f"[reuse] {checkpoint.name}: {len(labels)}", flush=True)
        else:
            labels = classify_batch(
                chunk, start, executable, args.model, args.max_budget_usd,
                args.timeout, args.retries,
            )
            checkpoint.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in labels),
                encoding="utf-8",
            )
            print(f"[ok] {checkpoint.name}: {len(labels)}", flush=True)
        all_labels.extend(labels)
    expected_all = set(range(len(rows)))
    errors = validate_labels(all_labels, expected_all)
    if errors:
        raise SystemExit(f"combined labels invalid: {errors}")
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_labels),
        encoding="utf-8",
    )
    print(f"classified {len(all_labels)} rows -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
