import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from build_ai_automation_history import build_observation, main  # noqa: E402


REVIEWS = {
    "reviewed_at": "2026-07-29",
    "strategic_thesis": {"headline": "governed harness", "confidence": "MEDIUM"},
    "reviews": [{
        "repo": "example/harness", "role": "harness-governance", "grade": "A",
        "recommendation": "pilot", "commit": "a" * 40, "stars_snapshot": 10,
    }],
}


class AiAutomationHistoryTests(unittest.TestCase):
    def test_first_observation_is_baseline_not_fake_trend(self):
        observation = build_observation("2026-07-29", REVIEWS, {}, None)
        self.assertEqual(observation["status"], "BASELINE_ONLY")
        self.assertEqual(observation["change_since_previous"]["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(observation["repo_metrics"][0]["metadata_source"], "review_snapshot")

    def test_cli_is_idempotent_for_same_day_and_does_not_backfill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviews = root / "reviews.json"
            snapshot = root / "snapshot.json"
            output = root / "history.json"
            reviews.write_text(json.dumps(REVIEWS), encoding="utf-8")
            snapshot.write_text(json.dumps({"repos": [{
                "repo": "example/harness", "stars": 11, "head_sha": "b" * 40,
            }]}), encoding="utf-8")
            self.assertEqual(main(["--date", "2026-07-29", "--reviews", str(reviews),
                                   "--snapshot", str(snapshot), "--output", str(output)]), 0)
            self.assertEqual(main(["--date", "2026-07-29", "--reviews", str(reviews),
                                   "--snapshot", str(snapshot), "--output", str(output)]), 0)
            saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(saved["started_at"], "2026-07-29")
        self.assertEqual(len(saved["observations"]), 1)
        self.assertTrue(saved["latest"]["repo_metrics"][0]["commit_drift"])


if __name__ == "__main__":
    unittest.main()
