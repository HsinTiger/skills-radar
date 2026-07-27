import sys
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from corpus_policy import (  # noqa: E402
    is_neutral,
    is_targeted,
    label_is_eligible,
    neutral_for,
    require_model_report_alignment,
    sample_kind,
)


class CorpusPolicyTests(unittest.TestCase):
    def test_neutral_accepts_only_missing_empty_or_explicit_neutral(self):
        for value in (None, "", "neutral"):
            row = {} if value is None else {"sample": value}
            self.assertTrue(is_neutral(row))
            self.assertEqual(sample_kind(row), "neutral")

    def test_every_targeted_topic_is_excluded(self):
        for value in ("targeted-eda", "targeted-eda2", "targeted-wifi", "targeted-future"):
            row = {"sample": value}
            self.assertTrue(is_targeted(row))
            self.assertFalse(is_neutral(row))

    def test_unknown_sample_kind_fails_closed(self):
        row = {"sample": "experimental"}
        self.assertEqual(sample_kind(row), "unknown")
        self.assertFalse(is_neutral(row))
        self.assertFalse(is_targeted(row))

    def test_legacy_human_label_is_eligible(self):
        self.assertTrue(label_is_eligible({"domain": "security"}, "domain"))
        self.assertTrue(label_is_eligible(
            {"domain": "security", "label_source": "llm"}, "domain"
        ))

    def test_model_confidence_is_field_specific(self):
        row = {
            "sample": "neutral",
            "label_source": "model",
            "domain": "security",
            "domain_conf": 0.61,
            "task": "verify",
            "task_conf": 0.59,
        }
        self.assertTrue(neutral_for(row, "domain"))
        self.assertFalse(neutral_for(row, "domain", "task"))

    def test_consumers_do_not_special_case_one_target(self):
        for relative in ("bin/opportunity.py", "bin/build_site.py", "bin/eda_deepdive.py"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn('!= "targeted-eda"', text, relative)

    def test_stale_master_is_rejected_against_model_report(self):
        rows = [
            {"domain": "security"},
            {"domain": "security", "label_source": "model"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "model_report.json"
            report.write_text(
                json.dumps({"n_seed": 2, "n_predicted": 0}), encoding="utf-8"
            )
            with self.assertRaises(RuntimeError):
                require_model_report_alignment(rows, report)
            report.write_text(
                json.dumps({"n_seed": 1, "n_predicted": 1}), encoding="utf-8"
            )
            require_model_report_alignment(rows, report)


if __name__ == "__main__":
    unittest.main()
