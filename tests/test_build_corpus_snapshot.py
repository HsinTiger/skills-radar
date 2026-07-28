import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from build_corpus_snapshot import build  # noqa: E402


class CorpusSnapshotTests(unittest.TestCase):
    def test_snapshot_requires_alignment_and_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master.jsonl"
            report = root / "model_report.json"
            output = root / "master.jsonl.gz"
            rows = [
                {"repo": "a/b", "path": "SKILL.md", "domain": "hardware-eda", "label_source": "llm"},
                {"repo": "c/d", "path": "SKILL.md", "domain": "software-dev", "label_source": "model"},
            ]
            master.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            report.write_text(json.dumps({"n_seed": 1, "n_predicted": 1}), encoding="utf-8")
            manifest = build(master, report, output, "corpus-latest", "2026-07-28")
            self.assertEqual(manifest["counts"]["rows"], 2)
            with gzip.open(output, "rt", encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 2)

    def test_snapshot_rejects_stale_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master.jsonl"
            report = root / "model_report.json"
            output = root / "master.jsonl.gz"
            master.write_text(json.dumps({
                "repo": "a/b", "path": "SKILL.md", "domain": "hardware-eda", "label_source": "llm",
            }) + "\n", encoding="utf-8")
            report.write_text(json.dumps({"n_seed": 0, "n_predicted": 1}), encoding="utf-8")
            with self.assertRaises(ValueError):
                build(master, report, output, "corpus-latest", "2026-07-28")


if __name__ == "__main__":
    unittest.main()
