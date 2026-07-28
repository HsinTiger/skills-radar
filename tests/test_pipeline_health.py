import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from write_pipeline_health import build_health  # noqa: E402


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        path.write_text(str(value), encoding="utf-8")


class PipelineHealthTests(unittest.TestCase):
    def test_pass_requires_current_outputs_and_timescale_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "daily/2026-07-28.md", "daily")
            write(root / "research/insights/2026-07-28.md", "insight")
            write(root / "corpus/daily_skill_recommendations.json", {
                "report_date": "2026-07-28", "status": "READY_FOR_OWNER_REVIEW",
                "corpus_freshness": {"status": "CURRENT"},
            })
            write(root / "data/timescale_summary_status.json", {
                "run_date": "2026-07-28", "status": "AI_GENERATED", "updated_periods": [],
            })
            health = build_health("2026-07-28", privacy_passed=True, root=root, run_context="launchd")
        self.assertEqual(health["status"], "PASS")
        self.assertEqual(health["remote_publish"], "NOT_PROVEN_UNTIL_REMOTE_READBACK")
        self.assertEqual(health["schedule_contract"]["execution_context"], "launchd")

    def test_ai_block_is_partial_and_retried_not_false_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "daily/2026-07-28.md", "daily")
            write(root / "research/insights/2026-07-28.md", "insight")
            write(root / "corpus/daily_skill_recommendations.json", {
                "report_date": "2026-07-28", "status": "READY_FOR_OWNER_REVIEW",
                "corpus_freshness": {"status": "CURRENT"},
            })
            write(root / "data/timescale_summary_status.json", {
                "run_date": "2026-07-28", "status": "AI_BLOCKED", "updated_periods": [],
            })
            health = build_health("2026-07-28", privacy_passed=True, root=root)
        self.assertEqual(health["status"], "PARTIAL")
        self.assertEqual(health["gates"]["timescale_dispatch"], "AI_BLOCKED")

    def test_stale_recommendation_fails_core_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "daily/2026-07-28.md", "daily")
            write(root / "corpus/daily_skill_recommendations.json", {
                "report_date": "2026-07-28", "status": "PREVIEW_STALE_CORPUS",
            })
            write(root / "data/timescale_summary_status.json", {
                "run_date": "2026-07-28", "status": "NO_PERIOD_DUE",
            })
            health = build_health("2026-07-28", privacy_passed=True, root=root)
        self.assertEqual(health["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
