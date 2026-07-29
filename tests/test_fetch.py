import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from fetch import upsert_daily_history  # noqa: E402


class FetchHistoryTests(unittest.TestCase):
    def test_same_day_rerun_replaces_instead_of_double_counting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            upsert_daily_history(str(path), {"date": "2026-07-29", "stars": {"a": 1}})
            upsert_daily_history(str(path), {"date": "2026-07-29", "stars": {"a": 2}})
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows, [{"date": "2026-07-29", "stars": {"a": 2}}])

    def test_preexisting_duplicate_dates_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text(
                '{"date":"2026-07-26","v":1}\n{"date":"2026-07-26","v":2}\n',
                encoding="utf-8",
            )
            upsert_daily_history(str(path), {"date": "2026-07-29", "v": 3})
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows, [{"date": "2026-07-26", "v": 2}, {"date": "2026-07-29", "v": 3}])


if __name__ == "__main__":
    unittest.main()
