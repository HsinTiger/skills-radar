import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from build_editorial_evidence import build  # noqa: E402
from generate_ai_artifact import CONFIG, validate_editorial  # noqa: E402
from render_editorial import markdown_body, render_all  # noqa: E402


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class EditorialEvidenceTests(unittest.TestCase):
    def fixture(self, root: Path):
        write(root / "data/corpus_update_manifest.json", {
            "run_date": "2026-07-28", "status": "SUCCESS", "collector": "test",
            "before": {"rows": 1}, "after": {"rows": 1}, "new_rows": 0,
            "delta_rows": 0, "run_context": "launchd", "claim_boundary": "bounded",
        })
        category = {"label": "label", "summary": "summary", "scope": "scope", "excluded_scope": "excluded", "recommendations": []}
        write(root / "corpus/daily_skill_recommendations.json", {
            "report_date": "2026-07-28", "status": "READY_FOR_OWNER_REVIEW",
            "corpus_freshness": {"status": "CURRENT"},
            "categories": {"EDA_IC": category, "finance-investing": category},
        })
        record = {"status": "AI_GENERATED", "period": {"period_id": "p"}, "ai": {}, "evidence": {}}
        write(root / "data/timescale_summaries.json", {"latest": {"day": record}})
        write(root / "data/timescale_summary_status.json", {"run_date": "2026-07-28", "status": "NO_PERIOD_DUE"})
        write(root / "corpus/opportunity.json", {
            "n_total": 1, "eligibility": {}, "global_production_pct": 42.3,
            "global_task_pct": {}, "B1_task_gaps": [], "B2_unfinished": [],
        })

    def test_build_requires_current_successful_corpus_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            result = build("2026-07-28", root)
            self.assertEqual(result["status"], "READY_FOR_AI_EDITORIAL")
            self.assertIn("C1", result["allowed_citations"])
            self.assertIn("T-day", result["allowed_citations"])
            self.assertEqual(result["citation_labels"]["今日採集"], "C1")
            manifest = root / "data/corpus_update_manifest.json"
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["status"] = "FAILED"
            write(manifest, value)
            with self.assertRaises(ValueError):
                build("2026-07-28", root)

    def test_editorial_requires_blog_structure_citations_and_bounded_numbers(self):
        evidence = {
            "editorial_date": "2026-07-28",
            "allowed_citations": ["C1", "T-day", "R-EDA", "R-FIN", "Q"],
            "citation_labels": {
                "今日採集": "C1", "日觀察": "T-day", "EDA 清單": "R-EDA",
                "財經清單": "R-FIN", "資料限制": "Q",
            },
            "evidence_ledger": {
                "C1": {"daily_new_rows": 0},
                "Q": {"production_document_proxy_pct": 42.3},
            },
        }
        sections = "\n\n".join(CONFIG["editorial"]["required"])
        article = (
            "# Skills Radar 觀點 — 2026-07-28\n\n"
            "> 本文由 AI 依當日可查證資料生成；觀點不等於實際部署、晶片設計簽核或投資建議。\n\n"
            + sections
            + "\n\n"
            + ("這是一段以公開證據建立觀點、說明反方解釋與驗證方法的完整專欄文字。" * 35)
            + " 〔今日採集〕〔日觀察〕〔EDA 清單〕〔財經清單〕〔資料限制〕"
        )
        errors = validate_editorial(
            article, evidence, CONFIG["editorial"]["required"], CONFIG["editorial"]["min_chars"],
        )
        self.assertEqual(errors, [])
        broken = article + " 建議買進並保證獲利。新增統計 999%。"
        errors = validate_editorial(
            broken, evidence, CONFIG["editorial"]["required"], CONFIG["editorial"]["min_chars"],
        )
        self.assertTrue(any("trading" in error for error in errors))
        self.assertTrue(any("999" in error for error in errors))
        safe = article.replace("完整專欄文字", "不提供買進指令的完整專欄文字", 1)
        errors = validate_editorial(
            safe, evidence, CONFIG["editorial"]["required"], CONFIG["editorial"]["min_chars"],
        )
        self.assertEqual(errors, [])

        positive = json.loads(json.dumps(evidence))
        positive["evidence_ledger"]["C1"]["daily_new_rows"] = 1
        false_zero = article + "\n\n今天的資料庫沒有新增一筆。"
        errors = validate_editorial(
            false_zero, positive, CONFIG["editorial"]["required"], CONFIG["editorial"]["min_chars"],
        )
        self.assertTrue(any("positive daily corpus delta" in error for error in errors))

    def test_renderer_escapes_raw_html_and_builds_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "research/editorials"
            output = root / "docs/editorials"
            source.mkdir(parents=True)
            (source / "2026-07-28.md").write_text(
                "# 標題\n\n## 核心觀點\n\n<script>alert(1)</script> 〔今日採集〕\n",
                encoding="utf-8",
            )
            entries = render_all(source, output)
            page = (output / "2026-07-28.html").read_text(encoding="utf-8")
            index = (output / "index.html").read_text(encoding="utf-8")
        self.assertEqual(entries[0]["date"], "2026-07-28")
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("2026-07-28.html", index)
        title, body = markdown_body("# T\n\n## S\n\nbody")
        self.assertEqual(title, "T")
        self.assertIn("<h2>S</h2>", body)


if __name__ == "__main__":
    unittest.main()
