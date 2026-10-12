import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import wiki_lint  # noqa: E402
from wiki_lint import collect  # noqa: E402


class WikiLintMetricTests(unittest.TestCase):
    def collect_text(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text(text, encoding="utf-8")
            return collect(path)

    def test_external_corpus_sizes_are_not_internal_corpus_metric(self):
        found = self.collect_text(
            "Snyk ToxicSkills 掃描 3,984 個 skill。\n"
            "GitHub 上有 246,584 個公開 SKILL.md。\n"
        )
        self.assertNotIn("語料規模", found)

    def test_internal_corpus_size_is_still_tracked(self):
        found = self.collect_text("目前語料共有 41,230 筆 skill 樣本。\n")
        self.assertEqual(found["語料規模"][0]["value"], 41230)


class WikiLintPublishedErrorTests(unittest.TestCase):
    def test_unreadable_history_keeps_local_path_out_of_published_errors(self):
        # corpus/wiki_lint.json 會公開：讀檔錯誤只留類別名，路徑只進本機紀錄。
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data" / "wiki_history.json").mkdir(parents=True)
            stderr = io.StringIO()
            with patch.object(wiki_lint, "ROOT", tmp), redirect_stderr(stderr):
                errors = wiki_lint.validate_entity_wiki()
        self.assertEqual(len(errors), 1)
        self.assertRegex(errors[0], r"^wiki history unreadable: \w+Error$")
        self.assertNotIn("wiki_history.json", errors[0])
        self.assertIn("wiki_history.json", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
