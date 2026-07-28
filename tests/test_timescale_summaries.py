import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from timescale_summaries import (  # noqa: E402
    build_period_evidence,
    due_periods,
    latest_complete_period,
    master_freshness,
    main,
    next_period,
    persist_results,
    validate_ai_output,
)


def row(**overrides):
    value = {
        "repo": "example/repo",
        "path": "skills/example/SKILL.md",
        "domain": "hardware-eda",
        "task": "verify",
        "maturity": "workflow",
        "target": "agent",
        "repo_created": "2026-06-15T00:00:00Z",
        "first_seen": "2026-06-20",
        "label_source": None,
        "sample": None,
        "name": "rtl-check",
        "description": "ASIC RTL formal verification",
        "body_head": "",
    }
    value.update(overrides)
    return value


def valid_summary(period):
    return {
        "scale": period["scale"],
        "period_id": period["period_id"],
        "headline": "結構轉向驗證與證據治理",
        "executive_summary": "史料 cohort 顯示能力結構改變，但新發現時鐘仍不足以證明採用趨勢。",
        "structural_changes": ["驗證類能力增加", "資料品質仍是主要限制"],
        "eda_ic_readout": "數位晶片內容應優先抽取可驗證程序，不能升格為工具簽核。",
        "finance_readout": "財經內容適合研究與資料檢核，不應直接產生交易決策。",
        "contrarian_view": "看似成長也可能只是公開來源與採集策略偏移。",
        "actions": ["保留證據卡並等待下一完整期比較"],
        "falsifiers": ["後續完整期未重現相同結構"],
        "caveats": ["公開語料低估企業內部使用"],
        "confidence": "MEDIUM",
        "evidence_ids": ["E1", "E3", "E8", "E9"],
    }


class TimescaleSummaryTests(unittest.TestCase):
    def test_complete_periods_use_previous_closed_interval(self):
        run = date(2026, 7, 28)
        self.assertEqual(latest_complete_period(run, "day")["period_id"], "2026-07-27")
        self.assertEqual(latest_complete_period(run, "week"), {
            "scale": "week", "period_id": "2026-W30", "start": "2026-07-20", "end": "2026-07-26",
        })
        self.assertEqual(latest_complete_period(run, "month")["period_id"], "2026-06")
        self.assertEqual(latest_complete_period(run, "quarter")["period_id"], "2026-Q2")

    def test_next_period_advances_all_calendar_scales(self):
        self.assertEqual(next_period({"scale": "week", "start": "2026-07-20", "end": "2026-07-26"})["start"], "2026-07-27")
        self.assertEqual(next_period({"scale": "month", "start": "2026-06-01", "end": "2026-06-30"})["period_id"], "2026-07")
        self.assertEqual(next_period({"scale": "quarter", "start": "2026-04-01", "end": "2026-06-30"})["period_id"], "2026-Q3")

    def test_initial_dispatcher_schedules_each_scale_once(self):
        history = {"periods": {s: {} for s in ("day", "week", "month", "quarter")}}
        due, backlog = due_periods(history, date(2026, 7, 28))
        self.assertEqual({p["scale"] for p in due}, {"day", "week", "month", "quarter"})
        self.assertTrue(all(value == 0 for value in backlog.values()))

    def test_dispatcher_catches_up_each_missing_day(self):
        old = latest_complete_period(date(2026, 7, 26), "day")
        history = {"periods": {
            "day": {old["period_id"]: {"status": "AI_GENERATED", "period": old}},
            "week": {}, "month": {}, "quarter": {},
        }}
        due, _ = due_periods(history, date(2026, 7, 29))
        days = [p["period_id"] for p in due if p["scale"] == "day"]
        self.assertEqual(days, ["2026-07-26", "2026-07-27", "2026-07-28"])

    def test_freshness_requires_seed_and_model_alignment(self):
        rows = [row(), row(label_source="model", domain_conf=0.9)]
        with tempfile.TemporaryDirectory() as tmp:
            master = Path(tmp) / "master.jsonl"
            master.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            fresh = master_freshness(rows, {"n_seed": 1, "n_predicted": 1}, master)
        self.assertEqual(fresh["status"], "CURRENT")

    def test_evidence_excludes_targeted_and_low_confidence_rows(self):
        period = latest_complete_period(date(2026, 7, 1), "month")
        rows = [
            row(),
            row(repo="targeted/repo", sample="targeted-eda"),
            row(repo="weak/repo", label_source="model", domain_conf=0.59),
        ]
        evidence = build_period_evidence(
            rows, period, {"status": "CURRENT"}, {"validation": {"status": "BLOCKED"}}, {},
        )
        self.assertEqual(evidence["evidence"]["E1_sample"]["archive_n"], 1)
        self.assertTrue(evidence["evidence"]["E10_quality"]["targeted_rows_excluded"])

    def test_ai_output_is_period_exact_and_number_free(self):
        period = latest_complete_period(date(2026, 7, 28), "week")
        valid = json.dumps({"summaries": [valid_summary(period)]}, ensure_ascii=False)
        self.assertEqual(validate_ai_output(valid, [period])[0]["period_id"], period["period_id"])
        broken = valid_summary(period)
        broken["headline"] = "成長百分之二十以上，約為 20%"
        with self.assertRaises(ValueError):
            validate_ai_output(json.dumps({"summaries": [broken]}, ensure_ascii=False), [period])

    def test_persist_is_append_only_by_period_id(self):
        period = latest_complete_period(date(2026, 7, 28), "day")
        evidence = {
            "period": period, "time_contract": {}, "evidence": {"E1_sample": {"archive_n": 1}},
        }
        history = {"periods": {s: {} for s in ("day", "week", "month", "quarter")}}
        result = persist_results(history, {"periods": [evidence]}, [valid_summary(period)], "2026-07-28")
        self.assertIn(period["period_id"], result["periods"]["day"])
        self.assertEqual(result["latest"]["day"]["status"], "AI_GENERATED")

    def test_cli_builds_all_due_scales_from_fresh_fixture(self):
        periods = [latest_complete_period(date(2026, 7, 28), scale)
                   for scale in ("day", "week", "month", "quarter")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master = root / "master.jsonl"
            rows = [
                row(repo=f"example/repo-{i}", path=f"skills/{i}/SKILL.md",
                    repo_created=created, first_seen="2026-07-27")
                for i, created in enumerate((
                    "2026-07-27T00:00:00Z", "2026-07-25T00:00:00Z",
                    "2026-06-15T00:00:00Z", "2026-05-15T00:00:00Z",
                ))
            ]
            master.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
            model = root / "model.json"
            model.write_text(json.dumps({"n_seed": 4, "n_predicted": 0}), encoding="utf-8")
            taxonomy = root / "taxonomy.json"; taxonomy.write_text("{}", encoding="utf-8")
            recommendations = root / "recommendations.json"; recommendations.write_text("{}", encoding="utf-8")
            ai = root / "ai.json"
            ai.write_text(json.dumps({"summaries": [valid_summary(p) for p in periods]}, ensure_ascii=False), encoding="utf-8")
            history = root / "history.json"; evidence = root / "evidence.json"; status = root / "status.json"
            rc = main([
                "--date", "2026-07-28", "--master", str(master),
                "--model-report", str(model), "--taxonomy-report", str(taxonomy),
                "--recommendations", str(recommendations), "--history", str(history),
                "--evidence-output", str(evidence), "--status-output", str(status),
                "--ai-output", str(ai),
            ])
            saved = json.loads(history.read_text(encoding="utf-8"))
            state = json.loads(status.read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(set(saved["latest"]), {"day", "week", "month", "quarter"})
        self.assertEqual(state["status"], "AI_GENERATED")

    def test_dashboard_exposes_quarter_and_dual_clock_contract(self):
        template = (ROOT / "index" / "site_template.html").read_text(encoding="utf-8")
        builder = (ROOT / "bin" / "build_site.py").read_text(encoding="utf-8")
        self.assertIn('id="btn-quarter"', template)
        self.assertIn("D.timescale_summary", template)
        self.assertIn("first_seen 是 radar 首次觀察", template)
        self.assertIn('"quarter": build_view("quarter", 12)', builder)


if __name__ == "__main__":
    unittest.main()
