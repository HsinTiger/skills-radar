#!/usr/bin/env python3
"""Render and validate the canonical macOS LaunchAgent contract."""

from __future__ import annotations

import argparse
import plistlib
from pathlib import Path


LABEL = "com.hsin.skills-radar"


def build_contract(repo_root: Path, runtime_path: str) -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(repo_root.resolve() / "bin" / "run_daily.sh")],
        "StartCalendarInterval": {"Hour": 8, "Minute": 30},
        "EnvironmentVariables": {
            "TZ": "Asia/Taipei",
            "PATH": runtime_path,
            "SKILLS_RADAR_RUN_CONTEXT": "launchd",
        },
        "ProcessType": "Background",
        "RunAtLoad": False,
    }


def validate_contract(contract: dict, repo_root: Path) -> list[str]:
    errors = []
    expected_program = ["/bin/bash", str(repo_root.resolve() / "bin" / "run_daily.sh")]
    if contract.get("Label") != LABEL:
        errors.append(f"Label must be {LABEL}")
    if contract.get("ProgramArguments") != expected_program:
        errors.append("ProgramArguments do not point to this checkout's bin/run_daily.sh")
    if contract.get("StartCalendarInterval") != {"Hour": 8, "Minute": 30}:
        errors.append("StartCalendarInterval must be daily 08:30")
    env = contract.get("EnvironmentVariables", {})
    if env.get("TZ") != "Asia/Taipei":
        errors.append("TZ must be Asia/Taipei")
    if env.get("SKILLS_RADAR_RUN_CONTEXT") != "launchd":
        errors.append("SKILLS_RADAR_RUN_CONTEXT must be launchd")
    if not env.get("PATH"):
        errors.append("PATH must preserve the installed AI/GitHub CLI providers")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-path", required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    if args.verify:
        with args.output.open("rb") as handle:
            contract = plistlib.load(handle)
        errors = validate_contract(contract, args.repo_root)
        if errors:
            for error in errors:
                print(f"launchd contract FAIL: {error}")
            return 1
        print(f"launchd contract PASS: {args.output}")
        return 0
    contract = build_contract(args.repo_root, args.runtime_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        plistlib.dump(contract, handle, sort_keys=False)
    print(f"launchd contract rendered: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
