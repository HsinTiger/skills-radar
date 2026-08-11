#!/usr/bin/env python3
"""Reject unexpected or executable paths before the unattended git publish step."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
ALLOWED = (
    re.compile(r"^README\.md$"),
    re.compile(r"^daily/\d{4}-\d{2}-\d{2}\.md$"),
    re.compile(r"^data/[A-Za-z0-9_.-]+\.(?:json|jsonl)$"),
    re.compile(r"^corpus/[A-Za-z0-9_.-]+\.json$"),
    re.compile(r"^research/(?:editorials|insights|recommendations|wiki|zones)/[A-Za-z0-9_./-]+\.md$"),
    re.compile(r"^docs/[A-Za-z0-9_./-]+\.(?:html|json|css|js)$"),
)


def _normalize(path: str) -> str | None:
    value = str(path).replace("\\", "/")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        return None
    return candidate.as_posix()


def validate_paths(paths: list[str], root: Path = ROOT) -> list[str]:
    errors = []
    for raw in sorted(set(paths)):
        path = _normalize(raw)
        if path is None or not any(pattern.fullmatch(path) for pattern in ALLOWED):
            errors.append(f"unexpected publish path: {raw}")
            continue
        local = root / Path(*PurePosixPath(path).parts)
        if local.exists() and local.is_symlink():
            errors.append(f"symlink publish path is forbidden: {path}")
    return errors


def _git_names(args: list[str], root: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="strict", timeout=30, check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def changed_paths(root: Path = ROOT, *, cached: bool = False) -> list[str]:
    if cached:
        return _git_names(["diff", "--cached", "--name-only", "--relative"], root)
    paths = _git_names(["diff", "--name-only", "--relative"], root)
    paths += _git_names(["ls-files", "--others", "--exclude-standard"], root)
    return sorted(set(paths))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cached", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    paths = changed_paths(args.root, cached=args.cached)
    errors = validate_paths(paths, args.root)
    if errors:
        print("publish scope BLOCKED:")
        for error in errors:
            print(f"- {error}")
        return 2
    print(f"publish scope PASS: {len(paths)} path(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
