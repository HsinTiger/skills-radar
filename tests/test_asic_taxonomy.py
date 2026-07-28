import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from asic_taxonomy import classify_row, is_hardware_candidate  # noqa: E402
from build_asic_catalog import alignment  # noqa: E402
from evaluate_asic_taxonomy import multilabel_metrics, scalar_metrics  # noqa: E402
from harvest_targeted import TOPICS, TOPIC_POLICY  # noqa: E402
from merge_asic_classified import validate_label  # noqa: E402
from sample_asic_labels import select  # noqa: E402
from sample_domain_labels import select as select_domain  # noqa: E402
from classify_domain_claude import validate_labels  # noqa: E402
from merge_classified import validate_classifications  # noqa: E402


def hardware_row(**overrides):
    row = {
        "domain": "hardware-eda",
        "label_source": "llm",
        "name": "sample",
        "description": "",
        "body_head": "",
        "path": "skills/sample/SKILL.md",
    }
    row.update(overrides)
    return row


class AsicTaxonomyTests(unittest.TestCase):
    def test_asic_rtl_and_wifi_baseband_is_direct(self):
        result = classify_row(hardware_row(
            name="wlan-rtl",
            description="802.11be OFDM baseband ASIC microarchitecture and synthesizable SystemVerilog RTL",
        ))
        self.assertEqual(result["hardware_target"], "asic")
        self.assertEqual(result["owner_fit"], "direct")
        self.assertEqual(result["provisional_grade"], "A")
        self.assertIn("rtl-design", result["asic_stages"])
        self.assertIn("microarchitecture", result["asic_stages"])
        self.assertIn("phy-baseband", result["wifi_areas"])
        self.assertIn("ofdm", result["wifi_areas"])

    def test_fpga_tool_flow_is_excluded_even_if_it_mentions_asic(self):
        result = classify_row(hardware_row(
            path="library/fpga/skills/systemverilog/SKILL.md",
            description="SystemVerilog for FPGA and ASIC with Vivado synthesis and bitstream generation",
        ))
        self.assertEqual(result["hardware_target"], "mixed")
        self.assertEqual(result["owner_fit"], "exclude")
        self.assertEqual(result["provisional_grade"], "D")

    def test_generic_sva_procedure_is_supporting(self):
        result = classify_row(hardware_row(
            name="assertion-design",
            description="SystemVerilog Assertions as executable specifications for RTL formal verification",
        ))
        self.assertEqual(result["hardware_target"], "generic")
        self.assertEqual(result["owner_fit"], "supporting")
        self.assertIn("formal-assertion", result["asic_stages"])

    def test_sampling_terms_do_not_become_taxonomy_evidence(self):
        result = classify_row(hardware_row(
            description="Generic RTL regression workflow",
            matched_terms=["WiFi 7", "OFDM", "channel estimation"],
            topic_tier=["phy-baseband"],
        ))
        self.assertEqual(result["wifi_areas"], [])

    def test_fixed_point_alone_is_not_called_wifi(self):
        result = classify_row(hardware_row(
            description="Fixed-point quantization and word-length analysis for a generic DSP datapath",
        ))
        self.assertIn("fixed-point", result["asic_stages"])
        self.assertEqual(result["wifi_areas"], [])

    def test_embedded_wifi_is_not_wifi_asic(self):
        result = classify_row(hardware_row(
            name="esp32-wifi",
            description="Flash ESP32 firmware and provision WiFi on an embedded board",
        ))
        self.assertEqual(result["hardware_target"], "embedded")
        self.assertEqual(result["owner_fit"], "exclude")

    def test_rf_frontend_is_excluded(self):
        result = classify_row(hardware_row(
            name="wifi-rf",
            description="WiFi RF front-end design with antenna matching and S-parameter analysis",
        ))
        self.assertEqual(result["hardware_target"], "analog-rf")
        self.assertEqual(result["owner_fit"], "exclude")
        self.assertIn("rf", result["wifi_areas"])

    def test_physical_design_is_adjacent(self):
        result = classify_row(hardware_row(
            name="openroad-flow",
            description="OpenROAD floorplan and place and route for standard-cell netlists",
        ))
        self.assertEqual(result["hardware_target"], "physical")
        self.assertEqual(result["owner_fit"], "adjacent")

    def test_low_confidence_model_row_fails_domain_gate(self):
        row = hardware_row(label_source="model", domain_conf=0.59)
        self.assertFalse(is_hardware_candidate(row))
        with self.assertRaises(ValueError):
            classify_row(row)

    def test_validated_llm_secondary_label_overrides_regex(self):
        result = classify_row(hardware_row(
            description="Vivado FPGA flow",
            asic_label_source="llm",
            hardware_target="generic",
            asic_stages=["formal-assertion"],
            wifi_areas=[],
            owner_fit="supporting",
            asic_label_evidence=["formal property"],
        ))
        self.assertEqual(result["hardware_target"], "generic")
        self.assertEqual(result["owner_fit"], "supporting")
        self.assertEqual(result["taxonomy_basis"], "llm-golden-v1")

    def test_synthesis_lec_eco_is_frontend_boundary_without_sta_power(self):
        result = classify_row(hardware_row(
            name="Frontend ECO equivalence",
            description="Design Compiler RTL synthesis, Formality LEC, and front-end ECO",
        ))
        self.assertIn("synthesis-lec-eco", result["asic_stages"])
        self.assertNotIn("synthesis-sta-power", result["asic_stages"])

    def test_owner_topics_do_not_search_excluded_areas(self):
        banned = ("fpga", "vivado", "quartus", "vitis", "xilinx", "esp32", "mcu",
                  "firmware", "pcb", "antenna", "s-parameter", "rf front")
        for topic in ("asic", "wifi-asic", "wifi"):
            self.assertIn(topic, TOPIC_POLICY)
            terms = " ".join(
                term.lower() for tier in TOPICS[topic].values() for term in tier
            )
            for word in banned:
                self.assertNotIn(word, terms, f"{topic} contains excluded search term {word}")
        asic_terms = " ".join(
            term.lower() for tier in TOPICS["asic"].values() for term in tier
        )
        self.assertIn("front end eco", asic_terms)
        for word in ("primetime", "place and route", "clock tree", "physical signoff"):
            self.assertNotIn(word, asic_terms)

    def test_strict_llm_label_validation(self):
        valid = {
            "i": 0,
            "hardware_target": "asic",
            "asic_stages": ["rtl-design"],
            "wifi_areas": ["phy-baseband"],
            "owner_fit": "direct",
            "evidence": ["ASIC", "RTL"],
            "injection_suspect": False,
        }
        self.assertEqual(validate_label(valid), [])
        invalid = {**valid, "hardware_target": "cpu", "asic_stages": ["rtl-design", "rtl-design"]}
        self.assertGreaterEqual(len(validate_label(invalid)), 2)
        inconsistent = {**valid, "hardware_target": "fpga", "owner_fit": "direct"}
        self.assertTrue(any("requires owner_fit=exclude" in error for error in validate_label(inconsistent)))

    def test_alignment_reports_stale_snapshot(self):
        rows = [hardware_row(), hardware_row(label_source="model", domain_conf=0.9)]
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "model_report.json"
            report.write_text(json.dumps({"n_seed": 2, "n_predicted": 0}), encoding="utf-8")
            status = alignment(rows, report)
        self.assertEqual(status["status"], "STALE")
        self.assertEqual(status["actual_seed"], 1)
        self.assertEqual(status["actual_model"], 1)

    def test_taxonomy_evaluation_metrics_are_auditable(self):
        scalar = scalar_metrics([("asic", "asic"), ("fpga", "generic")])
        self.assertEqual(scalar["accuracy"], 0.5)
        self.assertEqual(scalar["confusion"]["fpga"]["generic"], 1)
        multi = multilabel_metrics([(["rtl-design"], ["rtl-design"]), (["fixed-point"], [])])
        self.assertEqual(multi["exact_match"], 0.5)
        self.assertEqual(multi["per_label"]["fixed-point"]["fn"], 1)

    def test_golden_sample_is_deduplicated_and_scoped(self):
        rows = [
            hardware_row(name="one", description="ASIC RTL", sample="targeted-asic"),
            hardware_row(name="one", description="ASIC RTL", sample="targeted-asic"),
            hardware_row(name="two", description="SystemVerilog assertion", sample="targeted-wifi-asic"),
            hardware_row(name="three", description="ASIC RTL", sample="targeted-eda"),
        ]
        chosen = select(rows, {"targeted-asic", "targeted-wifi-asic"}, n=10, seed=0)
        self.assertEqual(len(chosen), 2)
        self.assertEqual({row["name"] for row in chosen}, {"one", "two"})

    def test_domain_sample_uses_only_unlabelled_new_topics(self):
        rows = [
            {"name": "one", "description": "ASIC RTL", "sample": "targeted-asic", "topic_tier": ["rtl-design"]},
            {"name": "one", "description": "ASIC RTL", "sample": "targeted-asic", "topic_tier": ["rtl-design"]},
            {"name": "two", "description": "OFDM RTL", "sample": "targeted-wifi-asic", "topic_tier": ["rtl-blocks"]},
            {"name": "three", "description": "ASIC", "sample": "targeted-asic", "domain": "hardware-eda"},
        ]
        chosen = select_domain(rows, {"targeted-asic", "targeted-wifi-asic"}, n=10, seed=0)
        self.assertEqual({row["name"] for row in chosen}, {"one", "two"})

    def test_domain_recovery_may_explicitly_audit_model_rows(self):
        rows = [
            {"name": "unlabelled", "description": "ASIC RTL", "sample": "targeted-asic"},
            {"name": "model", "description": "OFDM RTL", "sample": "targeted-wifi-asic",
             "domain": "software-dev", "label_source": "model"},
            {"name": "seed", "description": "ASIC", "sample": "targeted-asic",
             "domain": "hardware-eda", "label_source": "llm"},
        ]
        chosen = select_domain(
            rows, {"targeted-asic", "targeted-wifi-asic"}, n=10, seed=0,
            include_model=True,
        )
        self.assertEqual({row["name"] for row in chosen}, {"unlabelled", "model"})

    def test_generic_classifier_cleans_fresh_runs_and_validates_resume_outputs(self):
        script = (ROOT / "bin" / "classify.sh").read_text(encoding="utf-8")
        self.assertIn('if [ "$MODE" != "resume" ]', script)
        self.assertIn('rm -f "$OUTD"/*.jsonl "$OUTD"/*.raw', script)
        self.assertIn('if [ "$existing" -eq "$expected" ]', script)
        self.assertNotIn('[ -s "$OUTD/$base.jsonl" ]', script)

    def test_generic_merge_marks_new_labels_as_llm(self):
        script = (ROOT / "bin" / "merge_classified.py").read_text(encoding="utf-8")
        self.assertIn('row["label_source"] = "llm"', script)

    def test_generic_merge_rejects_missing_duplicate_and_invalid_labels(self):
        valid = {
            "i": 0, "domain": "hardware-eda", "profession": "IC 設計工程師",
            "task": "verify", "target": "team", "maturity": "workflow",
            "pain": "追查 RTL 失敗", "injection_suspect": False,
        }
        self.assertEqual(validate_classifications([valid], 1), [])
        errors = validate_classifications([valid, dict(valid)], 2)
        self.assertTrue(any("duplicate index" in error for error in errors))
        self.assertTrue(any("missing indices" in error for error in errors))
        errors = validate_classifications([dict(valid, domain="fpga")], 1)
        self.assertTrue(any("invalid domain" in error for error in errors))

    def test_recovery_label_validation_requires_complete_unique_enums(self):
        valid = [{
            "i": 0, "domain": "hardware-eda", "profession": "IC 設計工程師",
            "task": "verify", "target": "team", "maturity": "workflow",
            "pain": "手動追查 RTL 失敗", "injection_suspect": False,
        }]
        self.assertEqual(validate_labels(valid, {0}), [])
        invalid = [dict(valid[0], domain="fpga", i=1)]
        errors = validate_labels(invalid, {0})
        self.assertTrue(any("unexpected index" in error for error in errors))
        self.assertTrue(any("missing indices" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
