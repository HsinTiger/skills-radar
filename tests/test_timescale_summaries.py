import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

import timescale_summaries  # noqa: E402
from timescale_summaries import (  # noqa: E402
    build_period_evidence,
    due_periods,
    legacy_rewrite_periods,
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
        "executive_summary": "依專案建立日期歸入本期的樣本顯示能力結構改變，但新發現仍不足以證明採用趨勢。",
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


def cli_fixture(root, ai_text=None):
    """寫出四個尺度都到期的新鮮語料，回傳 main() 參數；ai_text 為 None 時走真的 provider 路徑。"""
    rows = [
        row(repo=f"example/repo-{i}", path=f"skills/{i}/SKILL.md",
            repo_created=created, first_seen="2026-07-27")
        for i, created in enumerate((
            "2026-07-27T00:00:00Z", "2026-07-25T00:00:00Z",
            "2026-06-15T00:00:00Z", "2026-05-15T00:00:00Z",
        ))
    ]
    (root / "master.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    (root / "model.json").write_text(json.dumps({"n_seed": 4, "n_predicted": 0}), encoding="utf-8")
    (root / "taxonomy.json").write_text("{}", encoding="utf-8")
    (root / "recommendations.json").write_text("{}", encoding="utf-8")
    args = [
        "--date", "2026-07-28", "--master", str(root / "master.jsonl"),
        "--model-report", str(root / "model.json"), "--taxonomy-report", str(root / "taxonomy.json"),
        "--recommendations", str(root / "recommendations.json"), "--history", str(root / "history.json"),
        "--evidence-output", str(root / "evidence.json"), "--status-output", str(root / "status.json"),
    ]
    if ai_text is not None:
        (root / "ai.json").write_text(ai_text, encoding="utf-8")
        args += ["--ai-output", str(root / "ai.json")]
    return args


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
        jargon = valid_summary(period)
        jargon["executive_summary"] = "archive_n 為空，因此引用 E1。"
        with self.assertRaisesRegex(ValueError, "internal field"):
            validate_ai_output(json.dumps({"summaries": [jargon]}, ensure_ascii=False), [period])
        process_jargon = valid_summary(period)
        process_jargon["executive_summary"] = "production workflow 已完成 validation。"
        with self.assertRaisesRegex(ValueError, "process jargon"):
            validate_ai_output(
                json.dumps({"summaries": [process_jargon]}, ensure_ascii=False), [period]
            )

    def test_legacy_prose_is_rescheduled_for_rewrite(self):
        period = latest_complete_period(date(2026, 7, 28), "day")
        stale = valid_summary(period)
        stale["headline"] = "repo_created cohort 沒有樣本"
        history = {"periods": {
            "day": {period["period_id"]: {
                "status": "AI_GENERATED", "period": period, "ai": stale,
            }},
            "week": {}, "month": {}, "quarter": {},
        }}
        due, backlog = legacy_rewrite_periods(history)
        self.assertEqual(due, [period])
        self.assertTrue(all(value == 0 for value in backlog.values()))

    def test_persist_uses_one_record_per_period_id(self):
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

    def test_provider_timeout_error_omits_local_command(self):
        # AI_BLOCKED 的 error 會進公開的 status 檔，不能帶出本機 CLI 路徑。
        local_cli = "/home/someone/node/bin/claude"
        timeout = timescale_summaries.subprocess.TimeoutExpired([local_cli, "--print"], 5)
        with patch.object(timescale_summaries.shutil, "which",
                          side_effect=lambda name: local_cli if name == "claude" else None), \
             patch.object(timescale_summaries.subprocess, "run", side_effect=timeout):
            with self.assertRaises(RuntimeError) as caught:
                timescale_summaries.invoke_ai({"periods": []}, timeout=5)
        self.assertEqual(str(caught.exception), "AI provider timed out after 5s")
        self.assertNotIn(local_cli, str(caught.exception))

    def test_provider_failure_keeps_cli_output_out_of_the_error(self):
        # CLI 的 stderr 可能帶出閘道網址或帳號資訊：只能進本機紀錄，不能進例外訊息。
        local_cli = "/home/someone/node/bin/claude"
        failed = timescale_summaries.subprocess.CompletedProcess(
            [local_cli], 1, "", "401 from https://gateway.example.internal for user someone",
        )
        stderr = io.StringIO()
        with patch.object(timescale_summaries.shutil, "which",
                          side_effect=lambda name: local_cli if name == "claude" else None), \
             patch.object(timescale_summaries.subprocess, "run", return_value=failed), \
             redirect_stderr(stderr):
            with self.assertRaises(RuntimeError) as caught:
                timescale_summaries.invoke_ai({"periods": []}, timeout=5)
        self.assertEqual(str(caught.exception), "AI provider failed rc=1")
        self.assertEqual(caught.exception.code, "PROVIDER_FAILED rc=1")
        self.assertIn("gateway.example.internal", stderr.getvalue())

    def test_blocked_status_file_holds_only_a_reason_code(self):
        local_cli = "/home/someone/node/bin/claude"
        failed = timescale_summaries.subprocess.CompletedProcess(
            [local_cli], 1, "", "401 from https://gateway.example.internal for user someone",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(timescale_summaries.shutil, "which",
                              side_effect=lambda name: local_cli if name == "claude" else None), \
                 patch.object(timescale_summaries.subprocess, "run", return_value=failed), \
                 redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = main(cli_fixture(root))
            text = (root / "status.json").read_text(encoding="utf-8")
        state = json.loads(text)
        self.assertEqual(rc, 0)
        self.assertEqual(state["status"], "AI_BLOCKED")
        self.assertEqual(state["error"], "PROVIDER_FAILED rc=1")
        self.assertNotIn("gateway.example.internal", text)
        self.assertNotIn(local_cli, text)

    def test_invalid_model_output_is_recorded_as_a_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with redirect_stdout(io.StringIO()):
                rc = main(cli_fixture(root, ai_text="model said: not json at all"))
            state = json.loads((root / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(state["error"], "OUTPUT_INVALID")

    def test_blocked_reason_codes(self):
        from security_gate import UntrustedContentError

        self.assertEqual(timescale_summaries.blocked_reason(UntrustedContentError("x")),
                         "SECURITY_GATE_REJECTED")
        self.assertEqual(timescale_summaries.blocked_reason(ValueError("x")), "OUTPUT_INVALID")
        self.assertEqual(timescale_summaries.blocked_reason(OSError("C:/x")), "INTERNAL_ERROR OSError")

    def test_dashboard_exposes_quarter_and_dual_clock_contract(self):
        # 前端已從單一 site_template.html 拆成多頁（index/site/），
        # 但契約不變：季尺度要在頁面上、雙時鐘要對讀者說明、
        # 資料不足與舊文重寫兩種狀態要有專屬文案、內部欄位不得外漏。
        site = ROOT / "index" / "site"
        home = (site / "page-home.html").read_text(encoding="utf-8")
        method = (site / "page-method.html").read_text(encoding="utf-8")
        script = (site / "radar.js").read_text(encoding="utf-8")
        builder = (ROOT / "bin" / "build_site.py").read_text(encoding="utf-8")
        self.assertIn('data-scale="quarter"', home)
        self.assertIn("D.timescale_summary", script)
        self.assertIn("repo_created", method)
        self.assertIn("first_seen", method)
        self.assertIn("兩個時鐘不能相加", method)
        self.assertIn("這一期資料不足，先不判讀趨勢", script)
        self.assertIn("這篇舊摘要正在重寫", script)
        self.assertNotIn("${x.delta_pp}pp", script)
        self.assertIn('"quarter": build_view("quarter", 12)', builder)
        self.assertFalse((ROOT / "index" / "site_template.html").exists(),
                         "舊單頁模板已淘汰，不應復活")


if __name__ == "__main__":
    unittest.main()
