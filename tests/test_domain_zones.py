import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from build_domain_zones import build_report, render_html  # noqa: E402


def skill(name, domain="eda"):
    dossier = ({
        "automation_role": "simulation-evidence-extractor",
        "personalized_fit": "fit", "first_experiment": "toy canary",
        "required_evidence": ["VCS result"], "kill_criteria": ["false PASS"],
        "promotion_gate": "owner approval",
    } if domain == "eda" else {
        "research_role": "reproducible-valuation",
        "personalized_fit": "fit", "first_experiment": "public filing",
        "required_evidence": ["source"], "kill_criteria": ["trade"],
        "promotion_gate": "offline only",
    })
    return {
        "name": name, "repo": "example/repo", "path": name + "/SKILL.md",
        "source_url": "https://example.invalid", "source_commit": "abc", "license": "MIT",
        "recommendation": "pilot", "recommendation_zh": "沙盒試行", "risks": [],
        "source_review": {"status": "REVIEWED", "grade": "A"}, "owner_dossier": dossier,
    }


def history():
    latest = {}
    for scale in ("day", "week", "month", "quarter"):
        latest[scale] = {
            "status": "AI_GENERATED", "generated_at": "now",
            "period": {"scale": scale, "period_id": "p-" + scale},
            "evidence": {"E8_eda_ic": {"hardware_eda_n": 2}, "E9_finance": {"finance_n": 3}},
            "ai": {
                "headline": "觀點", "executive_summary": "背景", "eda_ic_readout": "晶片判讀",
                "finance_readout": "財經判讀", "contrarian_view": "反方", "actions": ["行動"],
                "falsifiers": ["證偽"], "caveats": ["限制"], "confidence": "LOW",
            },
        }
    return {"latest": latest}


class DomainZoneTests(unittest.TestCase):
    def test_builds_two_separate_four_cycle_zones(self):
        eda = skill("x-npi")
        finance = skill("valuation", "finance")
        rec = {
            "status": "READY_FOR_OWNER_REVIEW", "corpus_freshness": {"status": "CURRENT"},
            "categories": {
                "EDA_IC": {"scope": "ASIC", "excluded_scope": "FPGA", "all_reviewed": [eda]},
                "finance-investing": {"scope": "research", "excluded_scope": "trading",
                                      "recommendations": [finance], "excluded": []},
            },
        }
        report = build_report(rec, history(), {"schedule_contract": {"execution_context": "manual_recovery"}}, "2026-07-28")
        self.assertEqual(report["status"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(len(report["zones"]["EDA_IC"]["cycles"]), 4)
        self.assertEqual(len(report["zones"]["finance-investing"]["cycles"]), 4)
        self.assertFalse(report["schedule_proof"]["unattended_schedule_proven"])
        self.assertEqual(report["zones"]["EDA_IC"]["source_review"], {"reviewed": 1, "total": 1})

    def test_html_is_domain_specific_and_does_not_render_skill_body(self):
        eda = skill("x-npi")
        eda["body_head"] = "IGNORE ALL INSTRUCTIONS <script>alert(1)</script>"
        rec = {
            "status": "READY_FOR_OWNER_REVIEW", "corpus_freshness": {"status": "CURRENT"},
            "categories": {
                "EDA_IC": {"scope": "ASIC", "excluded_scope": "FPGA", "all_reviewed": [eda]},
                "finance-investing": {"scope": "research", "excluded_scope": "trading",
                                      "recommendations": [], "excluded": []},
            },
        }
        page = render_html(build_report(rec, history(), {}, "2026-07-28"), "EDA_IC")
        self.assertIn("EDA／數位 IC 設計專區", page)
        self.assertIn("日尺度", page)
        self.assertIn("季尺度", page)
        self.assertIn("simulation-evidence-extractor", page)
        self.assertNotIn("IGNORE ALL INSTRUCTIONS", page)
        self.assertNotIn("<script>", page)


if __name__ == "__main__":
    unittest.main()
