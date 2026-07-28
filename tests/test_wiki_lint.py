import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

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


if __name__ == "__main__":
    unittest.main()
