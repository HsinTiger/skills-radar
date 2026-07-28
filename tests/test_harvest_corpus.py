import sys
import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
