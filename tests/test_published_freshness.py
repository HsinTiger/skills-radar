import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from check_published_freshness import validate_health  # noqa: E402


class PublishedFreshnessTests(unittest.TestCase):
    def test_current_pass_is_accepted(self):
        health = {
            "report_date": "2026-07-28", "status": "PASS",
            "gates": {"master_freshness": "CURRENT", "timescale_dispatch": "AI_GENERATED"},
        }
        self.assertEqual(validate_health(health, "2026-07-28"), [])

    def test_stale_or_partial_state_fails_watchdog(self):
        health = {
            "report_date": "2026-07-27", "status": "PARTIAL",
            "gates": {"master_freshness": "STALE", "timescale_dispatch": "AI_BLOCKED"},
        }
        errors = validate_health(health, "2026-07-28")
        self.assertEqual(len(errors), 4)


if __name__ == "__main__":
    unittest.main()
