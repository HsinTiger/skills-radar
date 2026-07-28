import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from update_corpus import run_update  # noqa: E402


class CorpusUpdateTests(unittest.TestCase):
    def make_root(self, tmp):
        root = Path(tmp)
        (root / "corpus").mkdir()
        (root / "data").mkdir()
        (root / "bin").mkdir()
        (root / "corpus/master.jsonl").write_text(
            json.dumps({"repo": "a/b", "path": "SKILL.md", "first_seen": "2026-07-27"}) + "\n",
            encoding="utf-8",
        )
        return root

    def test_success_distinguishes_real_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            collector = root / "bin/collector.py"
            collector.write_text(textwrap.dedent("""
                import json
                from pathlib import Path
                root = Path.cwd()
                row = {"repo": "c/d", "path": "skills/new/SKILL.md", "first_seen": "2026-07-28"}
                delta = root / "corpus/delta-2026-07-28.jsonl"
                delta.write_text(json.dumps(row) + "\\n", encoding="utf-8")
                with (root / "corpus/master.jsonl").open("a", encoding="utf-8") as out:
                    out.write(json.dumps(row) + "\\n")
                print(delta)
            """), encoding="utf-8")
            rc, manifest, delta = run_update(
                "2026-07-28", root, [sys.executable, str(collector)],
            )
        self.assertEqual(rc, 0)
        self.assertEqual(manifest["status"], "SUCCESS")
        self.assertEqual(manifest["new_rows"], 1)
        self.assertEqual(manifest["run_new_rows"], 1)
        self.assertTrue(delta.endswith("delta-2026-07-28.jsonl"))

    def test_collector_failure_is_not_zero_delta_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            collector = root / "bin/fail.py"
            collector.write_text("raise SystemExit(3)\n", encoding="utf-8")
            rc, manifest, delta = run_update(
                "2026-07-28", root, [sys.executable, str(collector)],
            )
            saved = json.loads((root / "data/corpus_update_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 3)
        self.assertEqual(delta, "")
        self.assertEqual(manifest["status"], "FAILED")
        self.assertEqual(saved["collector_exit_code"], 3)
        self.assertEqual(saved["new_rows"], 0)

    def test_successful_zero_delta_is_explicit_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            collector = root / "bin/no_delta.py"
            collector.write_text("raise SystemExit(0)\n", encoding="utf-8")
            rc, manifest, delta = run_update(
                "2026-07-28", root, [sys.executable, str(collector)],
            )
        self.assertEqual(rc, 0)
        self.assertEqual(delta, "")
        self.assertEqual(manifest["status"], "SUCCESS")
        self.assertEqual(manifest["new_rows"], 0)
        self.assertEqual(manifest["delta_rows"], 0)

    def test_same_day_rerun_preserves_existing_daily_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            row = {"repo": "c/d", "path": "skills/new/SKILL.md", "first_seen": "2026-07-28"}
            with (root / "corpus/master.jsonl").open("a", encoding="utf-8") as out:
                out.write(json.dumps(row) + "\n")
            (root / "corpus/delta-2026-07-28.jsonl").write_text(
                json.dumps(row) + "\n", encoding="utf-8",
            )
            collector = root / "bin/no_delta.py"
            collector.write_text("raise SystemExit(0)\n", encoding="utf-8")
            rc, manifest, delta = run_update(
                "2026-07-28", root, [sys.executable, str(collector)],
            )
        self.assertEqual(rc, 0)
        self.assertTrue(delta.endswith("delta-2026-07-28.jsonl"))
        self.assertEqual(manifest["new_rows"], 1)
        self.assertEqual(manifest["run_new_rows"], 0)
        self.assertTrue(manifest["reused_daily_delta"])

    def test_timeout_persists_failed_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self.make_root(tmp)
            collector = root / "bin/slow.py"
            collector.write_text("import time; time.sleep(2)\n", encoding="utf-8")
            rc, manifest, _ = run_update(
                "2026-07-28", root, [sys.executable, str(collector)], timeout_seconds=1,
            )
            saved = json.loads((root / "data/corpus_update_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 124)
        self.assertEqual(manifest["status"], "FAILED")
        self.assertIn("timed out", manifest["validation_error"])
        self.assertEqual(saved["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
