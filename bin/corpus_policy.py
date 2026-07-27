#!/usr/bin/env python3
"""Shared corpus eligibility rules for every statistical consumer.

The rules live here so a newly added ``targeted-*`` topic cannot silently leak
into population estimates.  Model-produced labels are usable only when the
confidence for the field being analysed reaches ``CONF_MIN``.
"""

import json
import os

CONF_MIN = 0.6


def sample_kind(row):
    """Return ``neutral``, ``targeted`` or ``unknown`` for one corpus row."""
    value = row.get("sample")
    if value in (None, "", "neutral"):
        return "neutral"
    if isinstance(value, str) and value.startswith("targeted-"):
        return "targeted"
    return "unknown"


def is_neutral(row):
    """Whether the row may contribute to population-level estimates."""
    return sample_kind(row) == "neutral"


def is_targeted(row):
    """Whether the row is a topic-oversampled observation."""
    return sample_kind(row) == "targeted"


def label_is_eligible(row, field, conf_min=CONF_MIN):
    """Whether ``field`` has a usable human/legacy or confident model label."""
    if not row.get(field):
        return False
    if row.get("label_source") != "model":
        # Legacy LLM seed rows predate label_source and are intentionally kept.
        return True
    try:
        return float(row.get(f"{field}_conf") or 0) >= conf_min
    except (TypeError, ValueError):
        return False


def neutral_for(row, *fields, conf_min=CONF_MIN):
    """Whether a row is neutral and eligible for all requested label fields."""
    return is_neutral(row) and all(
        label_is_eligible(row, field, conf_min=conf_min) for field in fields
    )


def require_model_report_alignment(rows, report_path):
    """Fail when a raw snapshot predates the tracked classifier report.

    Signal tables generated from an older Release can otherwise look valid while
    silently dropping later LLM seeds and using stale model predictions.
    """
    if not os.path.exists(report_path):
        raise RuntimeError(f"model report missing: {report_path}")
    with open(report_path, encoding="utf-8") as fh:
        report = json.load(fh)
    expected_seed = report.get("n_seed")
    expected_model = report.get("n_predicted")
    actual_seed = sum(bool(r.get("domain")) and r.get("label_source") != "model" for r in rows)
    actual_model = sum(r.get("label_source") == "model" for r in rows)
    if actual_seed != expected_seed or actual_model != expected_model:
        raise RuntimeError(
            "master/model_report mismatch: "
            f"master seed={actual_seed}, model={actual_model}; "
            f"report seed={expected_seed}, model={expected_model}. "
            "Refresh corpus/master.jsonl from the canonical runtime before rebuilding."
        )
