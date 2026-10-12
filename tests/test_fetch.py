import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import fetch  # noqa: E402
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


class FetchPublishedErrorTests(unittest.TestCase):
    """snapshot.json and facts-*.json are published, so raw error text stays in the local log."""

    def test_gh_failure_publishes_only_a_fixed_code(self):
        failed = subprocess.CompletedProcess(
            ["gh"], 1, "", "dial tcp 10.0.0.7:443 via /home/example-user/.config/gh failed",
        )
        stderr = io.StringIO()
        with patch.object(fetch.subprocess, "run", return_value=failed), redirect_stderr(stderr):
            result = fetch.gh("repos/example/repo")
        self.assertEqual(result, {"_error": "gh_failed rc=1"})
        self.assertIn("10.0.0.7", stderr.getvalue())

    def test_network_failure_publishes_only_the_exception_class(self):
        stderr = io.StringIO()
        error = OSError("resolved hn.algolia.com to 10.0.0.7 at /home/example-user")
        with patch.object(fetch, "fetch_bytes", side_effect=error), redirect_stderr(stderr):
            result = fetch.get_json("https://hn.algolia.com/api/v1/search_by_date")
        self.assertEqual(result, {"_error": "network_error OSError"})
        self.assertIn("10.0.0.7", stderr.getvalue())


class FetchPrivateRepoTests(unittest.TestCase):
    def test_community_search_asks_for_public_repos_and_drops_private_items(self):
        seen = {}

        def fake_gh(path, params=None):
            seen["q"] = params["q"]
            return {"items": [
                {"full_name": "someone/hidden", "private": True, "visibility": "private"},
                {"full_name": "someone/internal", "visibility": "internal"},
                {"full_name": "someone/open", "private": False, "visibility": "public",
                 "stargazers_count": 5, "created_at": "2026-07-28T00:00:00Z", "description": "x"},
            ]}

        with patch.object(fetch, "gh", side_effect=fake_gh):
            rows = fetch.fetch_new_community_skills(1)
        self.assertIn("is:public", seen["q"])
        self.assertEqual([row["repo"] for row in rows], ["someone/open"])

    def test_watched_repo_that_turned_private_publishes_no_details(self):
        with patch.object(fetch, "gh", return_value={"private": True, "stargazers_count": 9}) as gh:
            row = fetch.fetch_repo("someone/hidden", 1, "why", 1)
        self.assertEqual(row, {"repo": "someone/hidden", "tier": 1, "why": "why", "error": "not_public"})
        self.assertEqual(gh.call_count, 1)


if __name__ == "__main__":
    unittest.main()
