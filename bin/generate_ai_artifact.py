#!/usr/bin/env python3
"""Generate one validated Markdown artifact with agy or tool-less Claude CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
import os
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    "daily": {
        "prompt": ROOT / "index" / "prompt_daily.txt",
        "input": lambda day: ROOT / "data" / f"facts-{day}.json",
        "output": lambda day: ROOT / "daily" / f"{day}.md",
        "required": ("## 🎯 策略建議", "### 長期"),
        "min_chars": 800,
    },
    "insight": {
        "prompt": ROOT / "index" / "prompt_opportunity.txt",
        "input": lambda _day: ROOT / "corpus" / "opportunity.json",
        "output": lambda day: ROOT / "research" / "insights" / f"{day}.md",
        "required": ("## 二、沒人發現的機會", "## 四、中期看法"),
        "min_chars": 800,
    },
}


def validate_markdown(text: str, required: tuple[str, ...], min_chars: int) -> list[str]:
    errors = []
    if len(text.strip()) < min_chars:
        errors.append(f"artifact too short: {len(text.strip())} < {min_chars}")
    for heading in required:
        if heading not in text:
            errors.append(f"missing heading: {heading}")
    if text.lstrip().startswith("```"):
        errors.append("markdown must not be wrapped in a code fence")
    return errors


def invoke(prompt: str, provider: str, model: str, budget: float, timeout: int) -> str:
    agy = shutil.which("agy") if provider in {"auto", "agy"} else None
    claude = ((shutil.which("claude.cmd") or shutil.which("claude"))
              if provider in {"auto", "claude"} else None)
    if agy:
        command = [agy, f"--print={prompt}", "--mode=accept-edits"]
        input_text = None
    elif claude:
        command = [
            claude, "--print", "--bare", "--tools", "", "--model", model,
            "--effort", "low", "--max-budget-usd", str(budget),
            "--no-session-persistence", "--permission-mode", "dontAsk",
        ]
        input_text = prompt
    else:
        raise RuntimeError(f"AI provider not found: {provider}")
    result = subprocess.run(
        command, input=input_text, cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-500:]
        raise RuntimeError(f"AI provider failed rc={result.returncode}: {detail}")
    return result.stdout.strip() + "\n"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=tuple(CONFIG))
    parser.add_argument("--date", required=True)
    parser.add_argument("--provider", choices=("auto", "agy", "claude"), default="auto")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--max-budget-usd", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    config = CONFIG[args.kind]
    input_path = args.input or config["input"](args.date)
    output_path = args.output or config["output"](args.date)
    prompt = config["prompt"].read_text(encoding="utf-8").replace("YYYY-MM-DD", args.date)
    evidence = input_path.read_text(encoding="utf-8")
    text = invoke(prompt + "\n" + evidence, args.provider, args.model,
                  args.max_budget_usd, args.timeout)
    errors = validate_markdown(text, config["required"], config["min_chars"])
    if errors:
        raise SystemExit("artifact rejected: " + "; ".join(errors))
    write_atomic(output_path, text)
    print(f"{args.kind} artifact -> {output_path} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
