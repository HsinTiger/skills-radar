import io
import sys
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import harvest_corpus  # noqa: E402
import harvest_delta  # noqa: E402


class HarvestCorpusTests(unittest.TestCase):
    def test_code_search_query_is_url_encoded(self):
        path = harvest_corpus.search_path("<1000", 1)
        self.assertIn("%3C1000", path)
        self.assertNotIn("<1000", path)

    def test_gh_retries_after_a_stuck_call(self):
        stuck = subprocess.TimeoutExpired(["gh", "api"], 90)
        done = subprocess.CompletedProcess(["gh", "api"], 0, stdout='{"items": []}', stderr="")
        with patch.object(harvest_corpus.subprocess, "run", side_effect=[stuck, done]) as run, \
             patch.object(harvest_corpus.time, "sleep") as sleep, \
             redirect_stderr(io.StringIO()):
            result = harvest_corpus.gh("search/code?q=x")
        self.assertEqual(result, {"items": []})
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(20)

    def test_gh_gives_up_after_four_stuck_calls_without_leaking_the_command(self):
        stuck = subprocess.TimeoutExpired(["gh", "api", "C:/Users/example-user/secret-dir"], 90)
        with patch.object(harvest_corpus.subprocess, "run", side_effect=stuck) as run, \
             patch.object(harvest_corpus.time, "sleep"), \
             redirect_stderr(io.StringIO()) as log:
            result = harvest_corpus.gh("search/code?q=x")
        self.assertEqual(run.call_count, 4)
        self.assertEqual(result, {"_error": "gh timed out"})
        self.assertNotIn("secret-dir", log.getvalue())

    def test_search_api_error_is_not_interpreted_as_zero_results(self):
        with patch.object(harvest_corpus, "SIZE_BUCKETS", ["<1000"]), \
             patch.object(harvest_corpus, "gh", return_value={"_error": "decode failed"}):
            with self.assertRaisesRegex(RuntimeError, "decode failed"):
                harvest_corpus.search_skill_files()

    def test_empty_global_result_is_not_a_valid_incremental_success(self):
        with patch.object(harvest_corpus, "SIZE_BUCKETS", ["<1000"]), \
             patch.object(harvest_corpus, "gh", return_value={"total_count": 0, "items": []}):
            with self.assertRaisesRegex(RuntimeError, "without any SKILL.md"):
                harvest_corpus.search_skill_files()

    def test_code_search_drops_private_repositories(self):
        items = [
            {"repository": {"full_name": "someone/hidden", "private": True}, "path": "SKILL.md"},
            {"repository": {"full_name": "someone/internal", "visibility": "internal"}, "path": "SKILL.md"},
            {"repository": {"full_name": "someone/open", "private": False}, "path": "skills/a/SKILL.md"},
        ]
        with patch.object(harvest_corpus, "SIZE_BUCKETS", ["<1000"]), \
             patch.object(harvest_corpus, "gh", return_value={"items": items}), \
             patch.object(harvest_corpus.time, "sleep"), \
             redirect_stderr(io.StringIO()):
            found = harvest_corpus.search_skill_files()
        self.assertEqual(found, {"someone/open": ["skills/a/SKILL.md"]})

    def test_delta_never_fetches_or_stores_a_private_repository(self):
        skill = "---\nname: demo\ndescription: a plain demo skill used by tests\n---\nbody text for the demo\n"

        def fake_gh(path):
            if path == "repos/someone/hidden":
                return {"private": True, "visibility": "private"}
            return {"private": False, "visibility": "public", "stargazers_count": 1}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "corpus").mkdir()
            master = root / "corpus" / "master.jsonl"
            master.write_text(json.dumps({"repo": "owner/old", "path": "SKILL.md"}) + "\n", encoding="utf-8")
            found = {"someone/hidden": ["SKILL.md"], "someone/open": ["SKILL.md"]}
            with patch.object(harvest_delta, "CORPUS", str(root / "corpus")), \
                 patch.object(harvest_delta, "MASTER", str(master)), \
                 patch.object(harvest_delta, "SEEN", str(root / "corpus" / "seen.tsv")), \
                 patch.object(harvest_delta, "SECURITY_MANIFEST", str(root / "data" / "security.json")), \
                 patch.object(harvest_delta.hc, "search_skill_files", return_value=found), \
                 patch.object(harvest_delta.hc, "gh", side_effect=fake_gh), \
                 patch.object(harvest_delta.hc, "fetch_raw", return_value=skill) as fetch_raw, \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                harvest_delta.main()
            repos = [json.loads(line)["repo"] for line in master.read_text(encoding="utf-8").splitlines()]
        fetch_raw.assert_called_once_with("someone/open", "SKILL.md")
        self.assertEqual(repos, ["owner/old", "someone/open"])

    def test_canonical_master_recovers_seen_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master.jsonl"
            master.write_text(
                json.dumps({"repo": "owner/repo", "path": "skills/a/SKILL.md"}) + "\n",
                encoding="utf-8",
            )
            with patch.object(harvest_delta, "MASTER", str(master)), \
                 patch.object(harvest_delta, "SEEN", str(root / "missing-seen.tsv")):
                seen = harvest_delta.load_seen()
        self.assertEqual(seen, {("owner/repo", "skills/a/SKILL.md")})

    def test_stale_seen_cache_cannot_hide_row_absent_from_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master.jsonl"
            seen_path = root / "seen.tsv"
            master.write_text(
                json.dumps({"repo": "owner/repo", "path": "skills/a/SKILL.md"}) + "\n",
                encoding="utf-8",
            )
            seen_path.write_text(
                "owner/repo\tskills/a/SKILL.md\nowner/ghost\tskills/missing/SKILL.md\n",
                encoding="utf-8",
            )
            with patch.object(harvest_delta, "MASTER", str(master)), \
                 patch.object(harvest_delta, "SEEN", str(seen_path)):
                seen = harvest_delta.load_seen()
        self.assertEqual(seen, {("owner/repo", "skills/a/SKILL.md")})

    def test_same_day_delta_merge_is_cumulative(self):
        with tempfile.TemporaryDirectory() as tmp:
            delta = Path(tmp) / "delta.jsonl"
            first = {"repo": "owner/a", "path": "SKILL.md"}
            second = {"repo": "owner/b", "path": "skills/b/SKILL.md"}
            delta.write_text(json.dumps(first) + "\n", encoding="utf-8")
            count = harvest_delta.merge_daily_delta(str(delta), [second])
            rows = [json.loads(line) for line in delta.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(count, 2)
        self.assertEqual(rows, [first, second])


if __name__ == "__main__":
    unittest.main()
