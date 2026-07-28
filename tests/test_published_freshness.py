import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from check_published_freshness import load_remote_health, validate_health  # noqa: E402


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


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

    def test_workflow_reads_live_pages_not_only_checkout(self):
        workflow = (ROOT / ".github" / "workflows" / "freshness-watch.yml").read_text(encoding="utf-8")
        self.assertIn("--health-url https://hsintiger.github.io/skills-radar/pipeline_health.json", workflow)

    @patch("check_published_freshness.urlopen")
    def test_live_readback_uses_cache_buster(self, mocked):
        mocked.return_value = FakeResponse(b'{"status":"PASS"}')
        self.assertEqual(load_remote_health("https://example.test/health.json"), {"status": "PASS"})
        request = mocked.call_args.args[0]
        self.assertIn("watchdog=", request.full_url)
        self.assertEqual(request.headers["Cache-control"], "no-cache")

    @patch("check_published_freshness.urlopen")
    def test_live_readback_rejects_non_200(self, mocked):
        mocked.return_value = FakeResponse(b"{}", status=503)
        with self.assertRaises(RuntimeError):
            load_remote_health("https://example.test/health.json")


if __name__ == "__main__":
    unittest.main()
