import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from extract_classification import extract  # noqa: E402


class ExtractClassificationTests(unittest.TestCase):
    def test_accepts_jsonl_and_fenced_array(self):
        rows = extract('{"i": 0}\n{"i": 1}\n')
        self.assertEqual([row["i"] for row in rows], [0, 1])
        rows = extract('```json\n[{"i": 0}, {"i": 1}]\n```')
        self.assertEqual([row["i"] for row in rows], [0, 1])

    def test_rejects_prose_without_objects(self):
        with self.assertRaises(ValueError):
            extract("分類完成，但沒有 JSON。")


if __name__ == "__main__":
    unittest.main()
