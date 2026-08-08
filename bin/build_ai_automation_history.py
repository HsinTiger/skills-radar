#!/usr/bin/env python3
"""Persist a truthful daily observation tape for the AI harness research zone.

The tape contains pinned review state plus metadata already collected by
``fetch.py``.  It never downloads or executes third-party code.  Historical
records start when this feature is introduced; absence before that date is not
backfilled as a fabricated daily observation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWS = ROOT / "corpus" / "ai_automation_skill_reviews.json"
SNAPSHOT = ROOT / "data" / "snapshot.json"
OUTPUT = ROOT / "data" / "ai_automation_history.json"


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_observation(run_date: str, reviews_doc: dict, snapshot: dict,
                      previous: dict | None = None) -> dict:
    reviews = reviews_doc.get("reviews", [])
    live = {item.get("repo"): item for item in snapshot.get("repos", [])}
    repo_metrics = []
    for review in reviews:
        repo = review.get("repo")
        fact = live.get(repo, {})
        stars = fact.get("stars")
        source = "daily_fact" if stars is not None else "review_snapshot"
        if stars is None:
            stars = review.get("stars_snapshot")
        repo_metrics.append({
            "repo": repo,
            "role": review.get("role"),
            "grade": review.get("grade"),
            "recommendation": review.get("recommendation"),
            "pinned_commit": review.get("commit"),
            "observed_head": fact.get("head_sha"),
            "commit_drift": (
                bool(fact.get("head_sha")) and fact.get("head_sha") != review.get("commit")
            ),
            "stars": stars,
            "pushed_at": fact.get("pushed_at"),
            "metadata_source": source,
        })
    repo_metrics.sort(key=lambda item: item.get("repo") or "")
    grade_counts = Counter(item.get("grade") for item in reviews)
    recommendation_counts = Counter(item.get("recommendation") for item in reviews)
    role_counts = Counter(item.get("role") for item in reviews)
    current_stars = {item["repo"]: item.get("stars") for item in repo_metrics}
    previous_stars = {
        item.get("repo"): item.get("stars")
        for item in (previous or {}).get("repo_metrics", [])
    }
    star_delta = {
        repo: value - previous_stars[repo]
        for repo, value in current_stars.items()
        if isinstance(value, int) and isinstance(previous_stars.get(repo), int)
    }
    evidence = {
        "reviewed_at": reviews_doc.get("reviewed_at"),
        "review_count": len(reviews),
        "grade_counts": dict(grade_counts),
        "recommendation_counts": dict(recommendation_counts),
        "role_counts": dict(role_counts),
        "repo_metrics": repo_metrics,
    }
    thesis = reviews_doc.get("strategic_thesis", {})
    return {
        "date": run_date,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "status": "BASELINE_ONLY" if previous is None else "DAILY_OBSERVATION",
        "history_days": 1 if previous is None else int(previous.get("history_days", 1)) + 1,
        "evidence_hash": _digest(evidence),
        "review_count": len(reviews),
        "grade_counts": dict(grade_counts),
        "recommendation_counts": dict(recommendation_counts),
        "role_counts": dict(role_counts),
        "repo_metrics": repo_metrics,
        "change_since_previous": {
            "status": "INSUFFICIENT_HISTORY" if previous is None else "COMPARABLE",
            "star_delta": star_delta,
            "source_drift_repos": [
                item["repo"] for item in repo_metrics if item.get("commit_drift")
            ],
        },
        "analysis": {
            key: thesis.get(key)
            for key in (
                "headline", "claim", "counterpoint", "potential_track",
                "owner_specialization", "catalysts", "leading_indicators",
                "falsifiers", "confidence", "history_boundary",
            )
        },
        "claim_boundary": (
            "GitHub metadata and static source review only; stars, commits and README claims do not prove adoption, "
            "security, runtime reliability, EDA correctness or business value"
        ),
    }


def update_history(history: dict, observation: dict) -> dict:
    records = list(history.get("observations", []))
    same = next((item for item in records if item.get("date") == observation["date"]), None)
    if same:
        if same.get("evidence_hash") == observation.get("evidence_hash"):
            observation["revision_history"] = same.get("revision_history", [])
        else:
            revisions = list(same.get("revision_history", []))
            revisions.append({
                "replaced_at": observation["observed_at"],
                "previous_evidence_hash": same.get("evidence_hash"),
                "reason": "same-day collected metadata or pinned review changed",
            })
            observation["revision_history"] = revisions
        records = [item for item in records if item.get("date") != observation["date"]]
    records.append(observation)
    records.sort(key=lambda item: item.get("date", ""))
    return {
        "schema_version": 1,
        "started_at": history.get("started_at") or observation["date"],
        "updated_at": observation["observed_at"],
        "observations": records,
        "latest": records[-1],
        "history_contract": (
            "append one real daily observation; same-day evidence changes retain a revision marker; "
            "never synthesize observations before started_at"
        ),
    }


def write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--reviews", type=Path, default=REVIEWS)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    reviews = load(args.reviews, {})
    if not reviews.get("reviews"):
        raise SystemExit("AI automation pinned reviews are required")
    history = load(args.output, {"schema_version": 1, "observations": []})
    previous = next(
        (item for item in reversed(history.get("observations", [])) if item.get("date") < args.date),
        None,
    )
    observation = build_observation(args.date, reviews, load(args.snapshot, {}), previous)
    updated = update_history(history, observation)
    write_atomic(args.output, updated)
    print(
        f"ai automation observation: {args.date}; status={observation['status']}; "
        f"reviews={observation['review_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
