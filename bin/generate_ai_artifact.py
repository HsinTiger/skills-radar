#!/usr/bin/env python3
"""Generate one validated Markdown artifact with agy or tool-less Claude CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import re
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
    "editorial": {
        "prompt": ROOT / "index" / "prompt_editorial.txt",
        "input": lambda _day: ROOT / "corpus" / "editorial_evidence.json",
        "output": lambda day: ROOT / "research" / "editorials" / f"{day}.md",
        "required": (
            "## 核心觀點", "## 資料庫今天發生什麼", "## 多尺度判讀",
            "## EDA／WiFi ASIC", "## 財經研究", "## AI Agent／Automation", "## 反方觀點",
            "## 接下來怎麼驗證", "## 證據與限制",
        ),
        "min_chars": 1000,
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


def _numbers(text: str) -> set[str]:
    return {
        token.replace(",", "").removesuffix("%")
        for token in re.findall(r"(?<![A-Za-z0-9_])\d+(?:,\d{3})*(?:\.\d+)?%?", text)
    }


def validate_editorial(text: str, evidence: dict, required: tuple[str, ...], min_chars: int) -> list[str]:
    errors = validate_markdown(text, required, min_chars)
    expected_title = f"# Skills Radar 觀點 — {evidence.get('editorial_date')}"
    if expected_title not in text:
        errors.append(f"missing exact title: {expected_title}")
    if "本文由 AI 依當日可查證資料生成" not in text:
        errors.append("missing AI/evidence disclosure")
    if len(text) > 12000:
        errors.append(f"editorial too long: {len(text)} > 12000")

    labels = evidence.get("citation_labels", {})
    allowed = set(labels)
    citations = set(re.findall(r"〔([^〕]+)〕", text))
    unknown = citations - allowed
    if unknown:
        errors.append(f"unknown evidence citations: {sorted(unknown)}")
    required_citations = {"今日採集", "EDA 清單", "財經清單", "AI 自動化清單", "資料限制"}
    missing = required_citations - citations
    if missing:
        errors.append(f"missing required evidence citations: {sorted(missing)}")
    if not citations.intersection({"日觀察", "週觀察", "月觀察", "季觀察"}):
        errors.append("missing timescale evidence citation")
    if re.search(r"\[(?:C1|T-(?:day|week|month|quarter)|R-(?:EDA|FIN)|Q)\]", text):
        errors.append("editorial exposes internal evidence keys")
    internal_terms = re.findall(
        r"\b(?:archive_n|discovered_n|new_rows|AI_GENERATED|READY_FOR_AI_EDITORIAL|"
        r"production_document_proxy|agent_target_proxy|evidence_ids|[A-Za-z]+_[A-Za-z0-9_]+)\b",
        text,
    )
    if internal_terms:
        errors.append(f"editorial exposes internal field names: {sorted(set(internal_terms))}")

    allowed_ascii = {"Skills", "Radar", "AI", "Agent", "Automation", "GitHub", "EDA", "WiFi", "ASIC", "RTL"}
    ascii_words = set(re.findall(r"[A-Za-z][A-Za-z-]*", text))
    unexplained = ascii_words - allowed_ascii
    if unexplained:
        errors.append(f"editorial contains reader-hostile English terms: {sorted(unexplained)}")
    if re.search(r"[\u4e00-\u9fff],[\u4e00-\u9fff]", text):
        errors.append("editorial uses ASCII punctuation inside Chinese prose")

    daily_new_rows = (evidence.get("evidence_ledger", {}).get("C1", {}) or {}).get("daily_new_rows")
    if isinstance(daily_new_rows, int) and daily_new_rows > 0:
        false_zero = ("今天的資料庫沒有新增一筆", "今日沒有新增一筆", "新增筆數為零", "有效的零增量")
        if any(phrase in text for phrase in false_zero):
            errors.append("editorial contradicts positive daily corpus delta")

    evidence_numbers = _numbers(json.dumps(evidence, ensure_ascii=False))
    unsupported = _numbers(text) - evidence_numbers
    if unsupported:
        errors.append(f"numeric claims absent from evidence: {sorted(unsupported)}")

    trade_text = re.sub(
        r"(?:不|不得|不可|不應|不能|避免|拒絕|禁止|不提供|不構成).{0,8}"
        r"(?:買進|賣出|做多|做空|下單|買賣|交易指令|投資建議)",
        "",
        text,
    )
    if re.search(r"買進|賣出|做多|做空|下單|保證獲利|必漲|必跌", trade_text):
        errors.append("editorial contains prohibited trading language")
    if re.search(r"<\s*(script|iframe|object)\b", text, re.I):
        errors.append("editorial contains raw active HTML")
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
    if args.kind == "editorial":
        evidence_doc = json.loads(evidence)
        errors = validate_editorial(text, evidence_doc, config["required"], config["min_chars"])
    else:
        errors = validate_markdown(text, config["required"], config["min_chars"])
    if errors:
        raise SystemExit("artifact rejected: " + "; ".join(errors))
    write_atomic(output_path, text)
    print(f"{args.kind} artifact -> {output_path} ({len(text)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
