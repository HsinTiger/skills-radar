import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import wiki_ingest as wiki  # noqa: E402
from wiki_ingest import append_snapshot, build_snapshot  # noqa: E402


class WikiIngestTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "domain": "security", "task": "verify", "maturity": "production",
                "target": "agent", "pain": "UNTRUSTED SECRET TEXT",
            },
            {
                "sample": "targeted-wifi", "domain": "security", "task": "generate",
                "maturity": "production", "target": "public",
            },
            {
                "sample": "neutral", "label_source": "model", "domain": "security",
                "domain_conf": 0.59, "task": "verify", "task_conf": 0.99,
                "maturity": "production", "maturity_conf": 0.99,
                "target": "agent", "target_conf": 0.99,
            },
        ]
        self.opportunity = {
            "global_production_pct": 100.0,
            "global_task_pct": {"verify": 100.0},
            "B1_task_gaps": [],
        }

    def test_snapshot_excludes_targeted_and_low_confidence_domain(self):
        snapshot = build_snapshot(self.rows, self.opportunity, "2026-07-27")
        self.assertEqual(snapshot["overall"]["n_total"], 1)
        self.assertEqual(snapshot["domains"]["security"]["n"], 1)

    def test_snapshot_never_copies_raw_third_party_text(self):
        snapshot = build_snapshot(self.rows, self.opportunity, "2026-07-27")
        self.assertNotIn("UNTRUSTED SECRET TEXT", json.dumps(snapshot))

    def test_same_date_change_requires_revision_note(self):
        first = build_snapshot(self.rows, self.opportunity, "2026-07-27")
        history = {"schema_version": 1, "snapshots": []}
        self.assertTrue(append_snapshot(history, first))
        changed = copy.deepcopy(first)
        changed["overall"]["n_total"] = 2
        with self.assertRaises(ValueError):
            append_snapshot(history, changed)
        self.assertTrue(append_snapshot(history, changed, "corrected sample policy"))
        self.assertEqual(history["snapshots"][-1]["revision"], 2)
        self.assertEqual(history["snapshots"][-1]["revision_note"], "corrected sample policy")

    def test_unchanged_same_date_is_idempotent(self):
        first = build_snapshot(self.rows, self.opportunity, "2026-07-27")
        history = {"schema_version": 1, "snapshots": []}
        append_snapshot(history, first)
        self.assertFalse(append_snapshot(history, copy.deepcopy(first)))
        self.assertEqual(len(history["snapshots"]), 1)

    def test_render_creates_entity_pages_without_raw_text(self):
        snapshot = build_snapshot(self.rows, self.opportunity, "2026-07-27")
        history = {"schema_version": 1, "snapshots": [snapshot]}
        old_research, old_docs = wiki.RESEARCH_WIKI, wiki.DOCS_WIKI
        try:
            with tempfile.TemporaryDirectory() as tmp:
                wiki.RESEARCH_WIKI = str(Path(tmp) / "research")
                wiki.DOCS_WIKI = str(Path(tmp) / "docs")
                wiki.render_research(history)
                wiki.render_docs(history)
                md = (Path(wiki.RESEARCH_WIKI) / "security.md").read_text(encoding="utf-8")
                page = (Path(wiki.DOCS_WIKI) / "security.html").read_text(encoding="utf-8")
                self.assertIn("OWNER-NOTES:START", md)
                self.assertIn("Evidence history", md)
                self.assertIn("neutral n=1", page)
                self.assertNotIn("UNTRUSTED SECRET TEXT", md + page)
        finally:
            wiki.RESEARCH_WIKI, wiki.DOCS_WIKI = old_research, old_docs


if __name__ == "__main__":
    unittest.main()
