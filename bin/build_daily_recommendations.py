#!/usr/bin/env python3
"""Build the daily owner-facing EDA/IC, finance, and AI harness recommendations.

This is a deterministic consumer of the radar corpus.  It never executes a
third-party skill, never treats repository popularity as correctness, and
keeps a stale corpus visible instead of silently presenting it as current.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "corpus" / "master.jsonl"
MODEL_REPORT = ROOT / "corpus" / "model_report.json"
ASIC_CATALOG = ROOT / "corpus" / "asic_skill_catalog.json"
ASIC_REVIEWS = ROOT / "corpus" / "asic_skill_reviews.json"
FINANCE_REVIEWS = ROOT / "corpus" / "finance_skill_reviews.json"
AI_AUTOMATION_REVIEWS = ROOT / "corpus" / "ai_automation_skill_reviews.json"
OUTPUT_JSON = ROOT / "corpus" / "daily_skill_recommendations.json"
RESEARCH_DIR = ROOT / "research" / "recommendations"
DOCS_DIR = ROOT / "docs" / "recommendations"

STATUS_ZH = {
    "adopt": "直接採用",
    "pilot": "沙盒試行",
    "watch": "觀察／待審",
    "exclude": "排除",
}

FINANCE_CAPABILITIES = {
    "thesis-research": {
        "weight": 32,
        "patterns": (
            r"investment thesis", r"thesis stress", r"source[- ]backed", r"evidence[- ]backed",
            r"supply[- ]chain", r"industry research", r"company research", r"產業鏈", r"供應鏈",
            r"投資論點", r"反證", r"深度調研",
        ),
        "summary": "建立可追溯的產業／公司投資論點、反證與待查證清單。",
        "use": "只作研究排序與論點壓力測試；結論必須回到一手來源。",
    },
    "fundamental-valuation": {
        "weight": 30,
        "patterns": (
            r"\bdcf\b", r"discounted cash flow", r"intrinsic value", r"fundamental analysis",
            r"ratio analysis", r"financial statement", r"earnings quality", r"owner earnings",
            r"valuation", r"估值", r"財務報表", r"基本面", r"現金流", r"財報",
        ),
        "summary": "協助財報正規化、基本面檢核與估值假設展開。",
        "use": "把假設、公式、來源與敏感度分開；不得把單一估值當成價格預測。",
    },
    "market-macro-data": {
        "weight": 24,
        "patterns": (
            r"market data", r"macro data", r"macroeconomic", r"economic data", r"yfinance",
            r"ohlcv", r"financial data", r"price data", r"market-data", r"總經", r"宏觀",
            r"市場資料", r"行情資料",
        ),
        "summary": "取得並正規化市場／總經資料，保留時間戳、來源與缺值狀態。",
        "use": "先做資料 readback 與 corporate-action 檢查，再供研究模型使用。",
    },
    "forensic-risk": {
        "weight": 28,
        "patterns": (
            r"forensic", r"earnings quality", r"risk analysis", r"risk management",
            r"fraud", r"irregularit", r"discrepanc", r"stress test", r"風險", r"舞弊",
            r"異常", r"壓力測試",
        ),
        "summary": "檢查財報異常、盈餘品質、風險因子與反方證據。",
        "use": "輸出證據與不確定性，不把規則式異常直接定性為舞弊。",
    },
    "backtest-research": {
        "weight": 20,
        "patterns": (r"backtest", r"factor analysis", r"factor model", r"benchmark", r"回測", r"因子"),
        "summary": "用回測與基準比較檢查研究假說。",
        "use": "必須揭露樣本外、交易成本、資料洩漏與存活者偏差；回測不等於獲利證明。",
    },
    "accounting-control": {
        "weight": 31,
        "patterns": (
            r"reconcil", r"general ledger", r"subledger", r"cashflow review", r"double-entry",
            r"financial reporting", r"對帳", r"總帳", r"會計", r"現金流檢核",
        ),
        "summary": "執行對帳、現金流與財務報表的一致性檢查。",
        "use": "適合作為研究資料品質 gate，不取代會計師簽核。",
    },
}

PREDICTION_PATTERNS = (
    r"next[- ]day", r"price prediction", r"predict.*(?:price|stock|market)", r"buy signal",
    r"sell signal", r"actionable trading", r"trading recommendation", r"次日.*預測",
    r"買入信號", r"賣出信號", r"交易建議", r"漲跌.*概率",
)
EXECUTION_PATTERNS = (
    r"execute (?:a )?trade", r"place (?:an )?order", r"submit (?:an )?order", r"live trading",
    r"real[- ]money", r"connect (?:a )?wallet", r"swap (?:token|crypto)", r"automated trading",
    r"brokerage account", r"實盤", r"下單", r"自動交易", r"連接錢包", r"代幣交換",
)
CREDENTIAL_PATTERNS = (
    r"private key", r"seed phrase", r"broker.*credential", r"broker.*api key",
    r"wallet.*api key", r"券商.*憑證", r"錢包.*私鑰",
)
RESEARCH_ONLY_PATTERNS = (
    r"research (?:support|only)", r"no trade execution", r"not financial advice",
    r"does not provide financial advice", r"for research purposes", r"僅供研究",
    r"不執行交易", r"非投資建議",
)


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def snapshot_freshness(rows: list[dict], report: dict, master_path: Path) -> dict:
    actual_seed = sum(bool(r.get("domain")) and r.get("label_source") != "model" for r in rows)
    actual_model = sum(r.get("label_source") == "model" for r in rows)
    expected_seed = report.get("n_seed")
    expected_model = report.get("n_predicted")
    current = actual_seed == expected_seed and actual_model == expected_model
    digest = hashlib.sha256(master_path.read_bytes()).hexdigest()
    return {
        "status": "CURRENT" if current else "STALE",
        "master_sha256": digest,
        "actual": {"rows": len(rows), "seed": actual_seed, "model": actual_model},
        "expected": {"seed": expected_seed, "model": expected_model},
        "population_claims_allowed": False,
        "note": (
            "master 與 model report 對齊；推薦仍只是候選排序，不是採用或正確性證明。"
            if current else
            "master 與 model report 不對齊；本次只能作預覽，需由 canonical runtime 刷新後再決策。"
        ),
    }


def catalog_freshness(catalog: dict, freshness: dict) -> dict:
    snapshot = catalog.get("snapshot", {})
    current = (
        catalog.get("status") == "CURRENT_CANDIDATE_CATALOG"
        and snapshot.get("sha256") == freshness.get("master_sha256")
        and snapshot.get("model_alignment", {}).get("status") == "CURRENT"
    )
    return {
        "status": "CURRENT" if current else "STALE",
        "catalog_status": catalog.get("status", "MISSING"),
        "catalog_sha256": snapshot.get("sha256"),
        "master_sha256": freshness.get("master_sha256"),
        "taxonomy_validation": snapshot.get("taxonomy_validation", {}).get("status", "UNKNOWN"),
        "claim_boundary": "catalog CURRENT permits candidate routing only; taxonomy validation and EDA runtime are separate gates",
    }


def github_url(repo: str, path: str, commit: str | None) -> str:
    ref = commit if commit and commit != "UNKNOWN" else "HEAD"
    return f"https://github.com/{repo}/blob/{ref}/{quote(path, safe='/._-')}"


def _matches(text: str, patterns) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _eda_use(fit: list[str]) -> str:
    joined = " ".join(fit).lower()
    if any(x in joined for x in (
        "architecture", "microarchitecture", "fixed-point", "fixed point",
        "design intent", "rtl design", "systemverilog rtl", "spec",
    )):
        return "在寫 RTL 前引用：先凍結 spec、fixed-point、cycle/interface/reset contract，再產生 candidate RTL。"
    if any(x in joined for x in ("fsdb", "simulation", "vcs", "verdi", "coverage")):
        return "在正式 compile/sim 之後引用其 waveform、coverage 與 debug evidence contract。"
    if any(x in joined for x in ("cycle contract", "rtl design", "handoff")):
        return "在寫 RTL 前先固化 cycle contract；交接時分開結構、功能與 signoff 證據。"
    if any(x in joined for x in ("testbench", "scoreboard", "ready-valid")):
        return "用於 testbench checklist、bounded wait、scoreboard 與 payload integrity；重寫成既有 framework。"
    if any(x in joined for x in ("sva", "formal", "assertion")):
        return "只生成綁定 spec requirement 的 candidate property，再交由正式 formal flow 證明。"
    if any(x in joined for x in ("synthesis", "lint", "lec", "sdc")):
        return "引用 evidence manifest 與 claim boundary；命令、library、constraint 與 ECO/LEC 規則以 golden flow 為準。"
    return "只抽取可審查的 procedure/checklist，先在非機密 toy design 驗證。"


def _eda_owner_dossier(fit: list[str], recommendation: str) -> dict:
    """Translate a public skill review into the owner's ASIC automation contract.

    The result deliberately describes an adaptation role, never an instruction
    to install or execute third-party content in a company flow.
    """
    joined = " ".join(fit).lower()
    if any(word in joined for word in (
        "architecture", "microarchitecture", "fixed-point", "fixed point",
        "design intent", "rtl design", "systemverilog rtl", "spec-to-rtl",
    )):
        role = "design-intent-compiler"
        fit_reason = "最適合放在 RTL 之前，把 latency、reset、backpressure、fixed-point 與介面不變量編譯成可審查契約。"
        experiment = "以公開 toy datapath 建立一頁 design intent、cycle table、assertion candidates 與交接 manifest，再由另一個 agent 只靠 bundle 重現。"
        evidence = ["owner-approved design intent", "cycle-by-cycle trace", "interface/reset invariants", "handoff readback"]
    elif any(word in joined for word in ("fsdb", "simulation", "vcs", "verdi", "coverage")):
        role = "simulation-evidence-extractor"
        fit_reason = "最貼近你高頻的 VCS／Verdi 除錯與 coverage 證據整理，可先降低人工翻波形與重建上下文的成本。"
        experiment = "在公開 ready/valid toy datapath 上，以既有 compile/sim 命令產生 FSDB，再只讀抽取同一 clock edge 的事件與 coverage denominator。"
        evidence = ["工具版本與輸入 commit", "compile/sim exit status", "FSDB/API readback", "coverage denominator 與查詢 JSON"]
    elif any(word in joined for word in ("sva", "formal", "assertion", "property")):
        role = "spec-linked-property-candidate"
        fit_reason = "適合把 cycle contract 與不變量轉成候選 SVA，但必須保留 spec requirement、assume/assert/cover 與 vacuity 邊界。"
        experiment = "對公開 FIFO 或 ready/valid toy block 產生少量候選 property；owner 逐條連回 requirement，再由正式工具 proof。"
        evidence = ["requirement-to-property mapping", "assumption ledger", "proof engine/result", "vacuity 與 counterexample review"]
    elif any(word in joined for word in ("synthesis", "lint", "lec", "sdc", "inference")):
        role = "synthesis-evidence-governor"
        fit_reason = "可把 lint、綜合、LEC 與前端 ECO 的不同 claim 分層，防止單一綠燈被升格成 RTL 正確或後端 signoff。"
        experiment = "只移植 manifest 與 claim boundary 到公開 toy RTL；實際 library、constraint、ECO 與命令仍由既有 golden flow 提供。"
        evidence = ["RTL/filelist hash", "tool/library/constraint manifest", "synthesis/LEC/ECO 分離結果", "失敗條件與 artifact readback"]
    elif any(word in joined for word in ("testbench", "scoreboard", "ready-valid")):
        role = "testbench-contract-adapter"
        fit_reason = "能補強 bounded wait、payload integrity、scoreboard 與參數組合，適合變成跨 block 的 verification factory 元件。"
        experiment = "在既有 testbench framework 重寫 checklist，不帶入 repository helper；以 timeout、背壓、reset 與資料完整性 canary 驗證。"
        evidence = ["stimulus/seed manifest", "bounded timeout", "scoreboard mismatch log", "coverage 與 rerun readback"]
    elif any(word in joined for word in ("cycle contract", "rtl design", "spec", "handoff")):
        role = "design-intent-compiler"
        fit_reason = "最適合放在 RTL 之前，把 latency、reset、backpressure、fixed-point 與介面不變量編譯成可審查契約。"
        experiment = "以公開 toy datapath 建立一頁 design intent、cycle table、assertion candidates 與交接 manifest，再由另一個 agent 只靠 bundle 重現。"
        evidence = ["owner-approved design intent", "cycle-by-cycle trace", "interface/reset invariants", "handoff readback"]
    else:
        role = "procedure-review-candidate"
        fit_reason = "目前只能作 procedure 來源，尚未顯示足夠的 WiFi ASIC RTL 直接適配性。"
        experiment = "只在公開 toy design 做人工 source review，不安裝、不寫入 RTL、不連公司工具。"
        evidence = ["pinned source commit", "license", "review notes", "explicit non-adoption decision"]
    return {
        "automation_role": role,
        "personalized_fit": fit_reason,
        "first_experiment": experiment,
        "required_evidence": evidence,
        "promotion_gate": (
            "owner 核准後，先通過公開 toy design canary，再以核准的 deterministic bundle 進 NX；"
            "只有真實 VCS／Verdi／DC／Formality/LEC 或 ECO evidence 能提升對應 claim。"
        ),
        "kill_criteria": [
            "要求自動修改產品 RTL 或繞過 owner approval",
            "把 parser/lint/open-source PASS 宣稱成產品功能、PPA 或 signoff PASS",
            "無法 pin source/license，或需要外傳內部訊號、license、PDK、SDC 與報告內容",
        ],
        "portfolio_state": recommendation,
    }


def _eda_frontend_priority(fit: list[str]) -> tuple[int, str]:
    text = " ".join(fit).lower()
    if any(word in text for word in ("physical", "place", "route", "post-layout", "backend")):
        return -25, "超出前端範圍"
    if any(word in text for word in (
        "architecture", "microarchitecture", "fixed-point", "fixed point", "rtl design",
        "systemverilog rtl", "cycle contract", "spec-to-rtl",
    )):
        return 30, "前端核心：spec/fixed-point/microarchitecture/RTL"
    if any(word in text for word in ("sva", "formal", "assertion", "property")):
        return 20, "前端 formal/SVA"
    if any(word in text for word in ("eco", "equivalence", "lec", "lint", "cdc", "rdc")):
        return 24, "前端 quality/synthesis/ECO"
    if any(word in text for word in ("testbench", "uvm", "simulation", "vcs", "verdi", "fsdb")):
        return 15, "前端 simulation/debug"
    if "synthesis" in text:
        return 10, "前端邊界：logic synthesis"
    return 0, "支援性 procedure"


def _select_eda_portfolio(items: list[dict], limit: int = 8) -> list[dict]:
    """Keep the daily list lifecycle-complete instead of eight near-duplicates."""
    eligible = [item for item in items if item["recommendation"] != "exclude"]
    slots = (
        ("architecture", "microarchitecture", "fixed-point", "rtl design"),
        ("cdc", "rdc"),
        ("sva", "formal", "assertion", "property"),
        ("equivalence", "lec"),
        ("simulation", "vcs", "verdi", "fsdb", "waveform"),
        ("synthesis", "lint"),
    )
    selected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for patterns in slots:
        for item in eligible:
            key = (item.get("repo", ""), item.get("path", ""))
            text = " ".join(item.get("capabilities", [])).lower()
            if key not in seen and any(
                re.search(rf"\b{re.escape(pattern)}\b", text) for pattern in patterns
            ):
                selected.append(item)
                seen.add(key)
                break
    for item in eligible:
        key = (item.get("repo", ""), item.get("path", ""))
        if key not in seen:
            selected.append(item)
            seen.add(key)
        if len(selected) >= limit:
            break
    return selected[:limit]


def _finance_owner_dossier(capabilities: list[str], recommendation: str) -> dict:
    primary = capabilities[0] if capabilities else "research-source"
    specs = {
        "accounting-control": (
            "research-data-control", "先把對帳、現金流與報表一致性變成資料品質 gate。",
            "用公開財報與手工算例核對 period、currency、公式與例外，不接任何帳戶。",
        ),
        "thesis-research": (
            "thesis-and-disconfirmation", "最適合建立論點、反證、待查問題與來源鏈，降低只蒐集支持材料的偏誤。",
            "選一家公司公開 filing，讓第二位讀者只靠來源 ledger 重建正反論點。",
        ),
        "fundamental-valuation": (
            "reproducible-valuation", "可把財報正規化、估值假設與敏感度分開，讓結論可重算。",
            "以公開財報建立 baseline/bull/bear 三組假設，逐格保留來源、單位與公式。",
        ),
        "market-macro-data": (
            "market-data-provenance", "可補強價格與總經資料的 timestamp、revision、corporate action 與缺值 readback。",
            "以公開指數資料測試重抓、調整前後價格與缺值處理，禁止輸出交易訊號。",
        ),
        "forensic-risk": (
            "risk-and-counterevidence", "適合把異常訊號轉成待查證問題，而不是直接定性或下交易結論。",
            "用已公開的歷史案例檢查規則是否能分開 red flag、證據與仍未知事項。",
        ),
        "backtest-research": (
            "hypothesis-falsification", "只能用來反駁研究假說，不能把漂亮回測當成獲利證明。",
            "以固定公開資料重跑含成本與樣本外切分的 baseline，列出 leakage 與 survivorship 檢查。",
        ),
    }
    role, fit_reason, experiment = specs.get(primary, (
        "research-source", "目前只適合作為研究來源候選，尚未完成可採用性審查。",
        "pin commit 與 license，完成無工具執行的逐檔 source review。",
    ))
    return {
        "research_role": role,
        "personalized_fit": fit_reason,
        "first_experiment": experiment,
        "required_evidence": ["一手來源與時間戳", "公式/轉換 readback", "反方證據", "可由第二位讀者重算"],
        "promotion_gate": "source/security review → 無 credential 離線 canary → owner review；永不自動下單。",
        "kill_criteria": ["要求券商、錢包、API key、私鑰或 seed phrase", "直接輸出買賣指令", "以回測、stars 或模型分數承諾獲利"],
        "portfolio_state": recommendation,
    }


def _ai_automation_owner_dossier(role: str, recommendation: str) -> dict:
    specs = {
        "reach-routing": (
            "public-intake-router",
            "把網站能力視為可探測、可降級的 adapter，而不是讓 agent 自行繞過平台限制。",
            "只用公開 Web、RSS 與 GitHub fixture 建立 capability registry、doctor 與 ordered fallback；所有登入型 channel 保持停用。",
            ["adapter capability readback", "active backend and failure reason", "public-source provenance", "zero credential access"],
        ),
        "context-compression": (
            "reversible-context-layer",
            "長任務需要壓縮脈絡，但設計約束與失敗證據不能因省 token 被靜默丟失。",
            "在去識別化公開 trace 上做壓縮／不壓縮對照，逐項檢查 constraint retention、取回率與任務結果。",
            ["uncompressed holdout", "constraint-retention score", "retrieval log", "task outcome and token readback"],
        ),
        "harness-governance": (
            "harness-change-governor",
            "最貼近你要搭建的 ASIC automation：每次改 system rule、tool、memory 或 middleware 都有失敗證據、預期修復與回歸清單。",
            "以公開 toy RTL 任務建立最小 change manifest，讓另一個 agent 重跑前後版本並核對預測修復與回歸。",
            ["failure trace", "change manifest", "before/after task set", "rollback and owner disposition"],
        ),
        "durable-orchestration": (
            "durable-state-machine",
            "長時間 EDA 任務必須能 checkpoint、重試、取消與恢復，且流程真相不能只存在 agent 對話。",
            "用公開多步驟任務模擬中斷、重入與重複 side effect，驗證 checkpoint conformance 與 idempotence。",
            ["checkpoint schema", "resume trace", "idempotence key", "cancellation and recovery readback"],
        ),
        "observability-evaluation": (
            "evidence-and-eval-rail",
            "trace 只有在能連回輸入版本、工具呼叫、artifact 與評測 oracle 時才有工程價值。",
            "對公開 task set 收集已脫敏 trace，建立 failure taxonomy、eval linkage、retention 與 telemetry-off readback。",
            ["sanitized trace", "task/eval linkage", "retention policy", "telemetry and redaction readback"],
        ),
        "sandbox": (
            "least-privilege-execution",
            "agent 產生的命令需要隔離，但工程內網、EDA license 與機密資料不能送入外部 sandbox。",
            "只在公開 fixture 驗證 deny-by-default network、ephemeral credential、filesystem boundary 與 artifact export。",
            ["network policy", "filesystem boundary", "process and artifact manifest", "credential absence proof"],
        ),
        "tool-discovery": (
            "typed-tool-registry",
            "工具愈多，動態 discovery、allowlist、scope 與 version pin 比把所有工具描述塞進 prompt 更重要。",
            "建立兩個只讀 toy tools 與一個拒絕型 canary，驗證 schema discovery、root restriction 與 unknown-tool fail closed。",
            ["pinned server and schema", "allowlist readback", "root/scope restriction", "negative authorization test"],
        ),
        "integration-control-plane": (
            "approval-gated-tool-router",
            "可借用 runtime discovery 與 scoped session，但不能把外部帳號和不可逆 action 交給通用控制平面。",
            "以本地 mock tools 模擬 session、runtime discovery 與 owner approval；不連任何真實帳號或 hosted action。",
            ["local session scope", "tool allowlist", "approval receipt", "no external credential or side effect"],
        ),
    }
    internal_role, fit_reason, experiment, evidence = specs.get(role, (
        "review-candidate", "目前只有概念適配性，尚未形成可驗證的 harness contract。",
        "先完成 pinned source、license、dependency 與 threat-boundary review。",
        ["pinned source", "license", "dependency graph", "explicit non-adoption decision"],
    ))
    return {
        "harness_role": internal_role,
        "personalized_fit": fit_reason,
        "first_experiment": experiment,
        "required_evidence": evidence,
        "promotion_gate": (
            "public fixture source review → isolated canary → measurable failure/recovery evidence → owner approval → "
            "only then package a deterministic domain adapter; public results never prove internal EDA correctness"
        ),
        "kill_criteria": [
            "requires private-session cookies, automatic login, anti-bot or CAPTCHA bypass",
            "sends confidential context, RTL, logs, credentials, license data or tool reports to an external service",
            "cannot reproduce failure, rollback state, tool scope and exact artifact readback",
        ],
        "portfolio_state": recommendation,
    }


def build_ai_automation(reviews_doc: dict, freshness: dict) -> dict:
    grade_score = {"A": 100, "B": 75, "C": 45, "D": 0}
    role_priority = {
        "harness-governance": 20, "durable-orchestration": 18,
        "observability-evaluation": 16, "tool-discovery": 15,
        "sandbox": 14, "context-compression": 12,
        "reach-routing": 10, "integration-control-plane": 6,
    }
    items = []
    for review in reviews_doc.get("reviews", []):
        grade = review.get("grade", "D")
        recommendation = review.get("recommendation") or {
            "A": "pilot", "B": "watch", "C": "watch", "D": "exclude",
        }.get(grade, "exclude")
        role = review.get("role", "review-candidate")
        commit = review.get("commit") or "UNKNOWN"
        item = {
            "name": review.get("name") or Path(review.get("path", "README.md")).stem,
            "artifact_type": review.get("artifact_type", "unknown"),
            "repo": review.get("repo"), "path": review.get("path"),
            "source_commit": commit,
            "source_url": github_url(review.get("repo", ""), review.get("path", ""), commit),
            "license": review.get("license", "UNKNOWN"),
            "category": "ai-automation", "owner_fit": role,
            "recommendation": recommendation,
            "recommendation_zh": STATUS_ZH[recommendation],
            "score": grade_score.get(grade, 0) + role_priority.get(role, 0)
                     + (3 if review.get("commit_verified") else 0),
            "summary": review.get("decision", ""),
            "use_in_ai_automation": review.get("decision", ""),
            "capabilities": review.get("fit", []),
            "dependencies": review.get("dependencies", []),
            "risks": review.get("risk", []),
            "evidence": review.get("evidence", []),
            "stars_snapshot": review.get("stars_snapshot"),
            "source_review": {
                "status": "REVIEWED", "grade": grade,
                "reviewed_at": reviews_doc.get("reviewed_at"),
                "commit_verified": bool(review.get("commit_verified")),
                "runtime_proof": "NOT_RUN",
                "review_scope": "static pinned-source review; no third-party code or credential path executed",
            },
            "evidence_freshness": freshness["status"],
            "do_not_claim": [
                "stars and README claims are not adoption, reliability or security proof",
                "public canary does not prove internal engineering or EDA correctness",
            ],
        }
        item["owner_dossier"] = _ai_automation_owner_dossier(role, recommendation)
        items.append(item)
    items.sort(key=lambda x: (-x["score"], x.get("repo") or "", x.get("path") or ""))
    recommendations = [item for item in items if item["recommendation"] != "exclude"]
    excluded = [item for item in items if item["recommendation"] == "exclude"]
    counts = Counter(item["recommendation"] for item in items)
    return {
        "label": "AI 應用／Agent Harness／Automation",
        "scope": "公開資訊入口、context 管理、durable orchestration、tool discovery、evaluation/observability、sandbox 與 integration control plane。",
        "excluded_scope": "私人貼文、未授權登入、cookie/session 匯入、反反爬或 CAPTCHA 規避、不可逆外部 action，以及公司機密或 EDA 資料外傳。",
        "summary": (
            f"已完成 {len(items)} 個 pinned source review：{counts.get('pilot', 0)} 個可進入公開資料 canary、"
            f"{counts.get('watch', 0)} 個只觀察或抽取 contract、{counts.get('exclude', 0)} 個排除。"
        ),
        "recommendations": recommendations,
        "excluded": excluded,
        "all_reviewed": items,
        "strategic_thesis": reviews_doc.get("strategic_thesis", {}),
        "adoption_gate": "只抽取 contract → 公開 fixture canary → failure/recovery/evidence readback → owner 核准；不直接安裝第三方 bundle。",
    }
def build_eda(reviews_doc: dict, catalog_doc: dict, freshness: dict) -> dict:
    catalog = {(r.get("repo"), r.get("path")): r for r in catalog_doc.get("candidates", [])}
    items = []
    grade_score = {"A": 100, "B": 80, "C": 50, "D": 0}
    for review in reviews_doc.get("reviews", []):
        candidate = catalog.get((review.get("repo"), review.get("path")), {})
        grade = review.get("grade", "D")
        decision_text = review.get("decision", "")
        if grade in {"A", "B"}:
            recommendation = "pilot"
        elif grade == "D":
            recommendation = "exclude"
        elif grade == "C" and any(word in decision_text for word in ("不要安裝", "不納入", "不直接引用")):
            recommendation = "exclude"
        else:
            recommendation = "watch"
        commit = review.get("commit") or "UNKNOWN"
        owner_fit = review.get("owner_fit") or candidate.get("owner_fit") or (
            "direct" if grade == "A" else "exclude" if grade == "D" else "supporting"
        )
        frontend_priority, priority_reason = _eda_frontend_priority(review.get("fit", []))
        item = {
            "name": review.get("name") or candidate.get("name") or Path(review.get("path", "SKILL.md")).parent.name or "skill",
            "repo": review.get("repo"),
            "path": review.get("path"),
            "source_commit": commit,
            "source_url": github_url(review.get("repo", ""), review.get("path", ""), commit),
            "license": review.get("license", "UNKNOWN"),
            "category": "EDA_IC",
            "owner_fit": owner_fit,
            "recommendation": recommendation,
            "recommendation_zh": STATUS_ZH[recommendation],
            "score": (
                grade_score.get(grade, 0)
                + frontend_priority
                + (5 if owner_fit == "direct" else 0)
                + (3 if review.get("commit_verified") else 0)
            ),
            "frontend_priority": frontend_priority,
            "priority_reason": priority_reason,
            "summary": decision_text,
            "use_in_next_rtl_design": _eda_use(review.get("fit", [])),
            "capabilities": review.get("fit", []),
            "dependencies": review.get("dependencies", []),
            "risks": review.get("risk", []),
            "source_review": {
                "status": "REVIEWED",
                "grade": grade,
                "reviewed_at": reviews_doc.get("reviewed_at"),
                "commit_verified": bool(review.get("commit_verified")),
                "runtime_proof": "NOT_RUN",
            },
            "evidence_freshness": freshness["status"],
            "do_not_claim": [
                "source review 不等於 VCS/Verdi/DC/Formality/ECO runtime PASS",
                "parser、lint 或 open-source tool PASS 不等於產品 RTL 正確或 signoff",
            ],
        }
        item["owner_dossier"] = _eda_owner_dossier(item["capabilities"], recommendation)
        items.append(item)
    items.sort(key=lambda x: (-x["score"], x["repo"], x["path"]))
    recommendations = _select_eda_portfolio(items)
    excluded = [x for x in items if x["recommendation"] == "exclude"][:6]
    counts = Counter(x["recommendation"] for x in items)
    return {
        "label": "EDA / 數位 IC（WiFi baseband ASIC）",
        "scope": "規格、fixed-point、microarchitecture、RTL、lint/CDC/RDC、formal/SVA、VCS/Verdi、UVM、logic synthesis、LEC 與前端 ECO。",
        "excluded_scope": "FPGA/Vivado/Quartus/bitstream、MCU/firmware/embedded、board/PCB、analog/RF/antenna，以及 P&R/CTS/route/physical signoff。",
        "summary": (
            f"已審 {len(items)} 個來源；{counts.get('pilot', 0)} 個可沙盒試行、"
            f"{counts.get('watch', 0)} 個待補證據、{counts.get('exclude', 0)} 個排除。"
            f"本頁列出前 {len(recommendations)} 個非排除候選；完整 {len(items)} 個 dossier 見 EDA 專區。"
        ),
        "recommendations": recommendations,
        "excluded": excluded,
        "all_reviewed": items,
        "adoption_gate": "先抽取 procedure → owner 核准 → toy design canary → internal golden-flow proof → 才能採用。",
    }


def _finance_text(row: dict) -> str:
    return " ".join(str(row.get(k) or "") for k in ("name", "description", "pain", "body_head")).lower()


def _domain_eligible(row: dict) -> bool:
    if row.get("domain") != "finance-investing":
        return False
    if row.get("label_source") != "model":
        return True
    try:
        return float(row.get("domain_conf") or 0) >= 0.6
    except (TypeError, ValueError):
        return False


def classify_finance_candidate(row: dict, freshness: dict) -> dict | None:
    if not _domain_eligible(row):
        return None
    text = _finance_text(row)
    capabilities = [name for name, spec in FINANCE_CAPABILITIES.items() if _matches(text, spec["patterns"])]
    if not capabilities:
        return None
    capabilities.sort(key=lambda x: -FINANCE_CAPABILITIES[x]["weight"])
    primary = capabilities[0]
    research_only = _matches(text, RESEARCH_ONLY_PATTERNS)
    prediction = _matches(text, PREDICTION_PATTERNS)
    execution = _matches(text, EXECUTION_PATTERNS)
    credentials = _matches(text, CREDENTIAL_PATTERNS)
    injection = bool(row.get("injection_suspect"))
    # Explicit "no trade execution" is a useful boundary, not an execution feature.
    if research_only and re.search(r"no trade execution|不執行交易", text, re.I):
        execution = False

    score = max(FINANCE_CAPABILITIES[c]["weight"] for c in capabilities)
    score += min(15, int(math.log10(max(1, row.get("stars") or 0) + 1) * 4))
    score += 6 if research_only else 0
    score -= 20 if prediction else 0
    score -= 35 if execution else 0
    score -= 25 if credentials else 0

    risks = []
    if prediction:
        risks.append("含價格／方向預測或交易訊號語意；不得直接形成交易決策")
    if execution:
        risks.append("含交易執行或實盤語意")
    if credentials:
        risks.append("可能接觸券商、錢包、私鑰或 API credential")
    if injection:
        risks.append("corpus 規則式掃描標記 injection_suspect")
    if "backtest-research" in capabilities:
        risks.append("回測可能有資料洩漏、過度擬合、交易成本與存活者偏差")
    if not research_only:
        risks.append("未找到明確 research-only／no-trade boundary")

    if injection or execution or credentials:
        recommendation = "exclude"
    elif prediction or not research_only:
        recommendation = "watch"
    elif score >= 24:
        recommendation = "pilot"
    else:
        recommendation = "watch"

    source_commit = row.get("source_commit") or "UNKNOWN"
    item = {
        "name": row.get("name") or Path(row.get("path", "SKILL.md")).parent.name or "skill",
        "repo": row.get("repo"),
        "path": row.get("path"),
        "source_commit": source_commit,
        "source_url": github_url(row.get("repo", ""), row.get("path", ""), source_commit),
        "license": row.get("license") or "UNKNOWN",
        "category": "finance-investing",
        "owner_fit": "research-support",
        "recommendation": recommendation,
        "recommendation_zh": STATUS_ZH[recommendation],
        "score": score,
        "summary": FINANCE_CAPABILITIES[primary]["summary"],
        "use_in_investment_research": FINANCE_CAPABILITIES[primary]["use"],
        "capabilities": capabilities,
        "risks": risks,
        "source_review": {
            "status": "PENDING",
            "grade": None,
            "reviewed_at": None,
            "commit_verified": False,
            "runtime_proof": "NOT_RUN",
        },
        "evidence_freshness": freshness["status"],
        "evidence": {
            "first_seen": row.get("first_seen"),
            "label_source": row.get("label_source") or "legacy-llm",
            "domain_conf": row.get("domain_conf"),
            "stars_repo_level": row.get("stars") or 0,
        },
        "do_not_claim": [
            "不執行交易、不接觸券商帳號／錢包／credential",
            "回測、模型分數或 repo stars 不等於獲利、正確性或安全證明",
            "第三方輸出不得直接成為買賣指令",
        ],
        "_primary": primary,
    }
    item["owner_dossier"] = _finance_owner_dossier(capabilities, recommendation)
    return item


def apply_finance_review(item: dict, review: dict, reviewed_at: str | None) -> dict:
    """Apply a pinned, human-readable source review without executing the skill."""
    grade = review.get("grade", "D")
    decision = review.get("recommendation") or {
        "A": "pilot", "B": "watch", "C": "watch", "D": "exclude",
    }.get(grade, "exclude")
    item["recommendation"] = decision
    item["recommendation_zh"] = STATUS_ZH[decision]
    item["source_commit"] = review.get("commit") or item.get("source_commit") or "UNKNOWN"
    item["source_url"] = github_url(item.get("repo", ""), item.get("path", ""), item["source_commit"])
    item["license"] = review.get("license") or item.get("license") or "UNKNOWN"
    item["summary"] = review.get("decision") or item.get("summary")
    item["dependencies"] = review.get("dependencies", [])
    item["risks"] = list(dict.fromkeys(review.get("risk", []) + item.get("risks", [])))
    item["source_review"] = {
        "status": "REVIEWED",
        "grade": grade,
        "reviewed_at": reviewed_at,
        "commit_verified": bool(review.get("commit_verified")),
        "runtime_proof": "NOT_RUN",
        "review_scope": "static source review only; third-party instructions were not executed",
    }
    item["owner_dossier"] = _finance_owner_dossier(item.get("capabilities", []), decision)
    return item


def build_finance(rows: list[dict], freshness: dict, reviews_doc: dict | None = None) -> dict:
    reviews_doc = reviews_doc or {}
    reviews = {
        (review.get("repo"), review.get("path")): review
        for review in reviews_doc.get("reviews", [])
    }
    candidates = []
    seen = set()
    for row in rows:
        item = classify_finance_candidate(row, freshness)
        if not item:
            continue
        review = reviews.get((item.get("repo"), item.get("path")))
        if review:
            item = apply_finance_review(item, review, reviews_doc.get("reviewed_at"))
        key = (item["repo"], item["path"])
        if key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    candidates.sort(key=lambda x: (-x["score"], x["repo"] or "", x["path"] or ""))

    reviewed_candidates = [
        item for item in candidates
        if item.get("source_review", {}).get("status") == "REVIEWED"
    ]
    selection_pool = reviewed_candidates or candidates
    selected, repo_seen, capability_counts = [], set(), Counter()
    for item in selection_pool:
        if item["recommendation"] == "exclude" or item["repo"] in repo_seen:
            continue
        primary = item["_primary"]
        if capability_counts[primary] >= 2:
            continue
        selected.append(item)
        repo_seen.add(item["repo"])
        capability_counts[primary] += 1
        if len(selected) == 8:
            break
    excluded = [x for x in selection_pool if x["recommendation"] == "exclude"][:6]
    review_queue = [
        x for x in candidates
        if x.get("source_review", {}).get("status") != "REVIEWED"
        and x["recommendation"] != "exclude"
    ][:8]
    for item in selected + excluded + review_queue:
        item.pop("_primary", None)
    counts = Counter(x["recommendation"] for x in selected)
    return {
        "label": "財經投資研究",
        "scope": "市場／總經資料、財報與盈餘品質、估值、產業鏈論點、風險與回測方法。",
        "excluded_scope": "自動下單、實盤交易、券商／錢包／私鑰／credential 操作，以及無證據的獲利承諾。",
        "summary": (
            f"今日選出 {len(selected)} 個研究候選：{counts.get('pilot', 0)} 個沙盒試行、"
            f"{counts.get('watch', 0)} 個觀察；"
            f"{sum(x.get('source_review', {}).get('status') == 'REVIEWED' for x in selected)} 個已完成 pinned source review。"
        ),
        "recommendations": selected,
        "excluded": excluded,
        "review_queue": review_queue,
        "adoption_gate": "先 pin commit 與 license → source/security review → 無 credential 的離線資料 canary → owner 核准。",
    }


def _md_cell(value) -> str:
    if isinstance(value, list):
        value = "、".join(str(v) for v in value)
    return str(value or "—").replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict) -> str:
    freshness = report["corpus_freshness"]
    lines = [
        f"# 每日 Skill 建議採用清單 — {report['report_date']}",
        "",
        f"> 狀態：`{report['status']}`。{freshness['note']}",
        "> 財經清單只供研究工具評估，不構成投資建議，也不授權任何交易或 credential 操作。",
        "",
    ]
    for key in ("EDA_IC", "finance-investing", "ai-automation"):
        if key not in report["categories"]:
            continue
        category = report["categories"][key]
        lines += [
            f"## {category['label']}", "", category["summary"], "",
            f"範圍：{category['scope']}", "",
            f"排除：{category['excluded_scope']}", "",
            "| 建議 | Skill | 用途摘要 | 引用方式 | Source review / commit | 主要風險 |",
            "|---|---|---|---|---|---|",
        ]
        for item in category["recommendations"]:
            use = (item.get("use_in_next_rtl_design")
                   or item.get("use_in_investment_research")
                   or item.get("use_in_ai_automation"))
            review = item["source_review"]
            review_text = f"{review['status']}"
            if review.get("grade"):
                review_text += f" / {review['grade']}"
            review_text += f" / {item['source_commit']}"
            lines.append(
                "| " + " | ".join([
                    _md_cell(item["recommendation_zh"]),
                    f"[{_md_cell(item['name'])}]({item['source_url']})<br>{_md_cell(item['repo'])}",
                    _md_cell(item["summary"]), _md_cell(use), _md_cell(review_text),
                    _md_cell(item.get("risks", [])[:3]),
                ]) + " |"
            )
        lines += ["", f"採用 gate：{category['adoption_gate']}", ""]
        if category["excluded"]:
            lines += ["### 本日排除／不建議", ""]
            for item in category["excluded"]:
                lines.append(
                    f"- `{item['repo']}/{item['path']}`：{_md_cell(item.get('risks') or item.get('summary'))}"
                )
            lines.append("")
    lines += [
        "## 證據與限制", "",
        f"- master SHA-256：`{freshness['master_sha256']}`",
        f"- 實際 seed/model：{freshness['actual']['seed']} / {freshness['actual']['model']}",
        f"- model report 預期 seed/model：{freshness['expected']['seed']} / {freshness['expected']['model']}",
        "- 本報告不使用 targeted samples 推估母體比例；清單排名不是普及率、正確率或獲利率。",
        "- `pilot` 只代表可進入隔離評估，不代表已安裝、已上線或通過 EDA／金融正確性驗證。",
        "",
    ]
    return "\n".join(lines)


def render_html(report: dict) -> str:
    def esc(value):
        return html.escape(str(value or "—"))

    sections = []
    for key in ("EDA_IC", "finance-investing", "ai-automation"):
        if key not in report["categories"]:
            continue
        category = report["categories"][key]
        cards = []
        for item in category["recommendations"]:
            use = (item.get("use_in_next_rtl_design")
                   or item.get("use_in_investment_research")
                   or item.get("use_in_ai_automation"))
            risks = "".join(f"<li>{esc(r)}</li>" for r in item.get("risks", [])[:4]) or "<li>未驗證</li>"
            cards.append(f"""
<article class="card">
  <div><span class="status {esc(item['recommendation'])}">{esc(item['recommendation_zh'])}</span>
  <span class="review">{esc(item['source_review']['status'])}{' / ' + esc(item['source_review'].get('grade')) if item['source_review'].get('grade') else ''}</span></div>
  <h3><a href="{esc(item['source_url'])}">{esc(item['name'])}</a></h3>
  <p class="repo">{esc(item['repo'])} · commit {esc(item['source_commit'])}</p>
  <p>{esc(item['summary'])}</p><p><strong>引用：</strong>{esc(use)}</p>
  <details><summary>風險與限制</summary><ul>{risks}</ul></details>
</article>""")
        sections.append(f"""
<section><h2>{esc(category['label'])}</h2>
<p>{esc(category['summary'])}</p><p class="muted">範圍：{esc(category['scope'])}<br>排除：{esc(category['excluded_scope'])}</p>
<div class="grid">{''.join(cards)}</div><p class="gate"><strong>採用 gate：</strong>{esc(category['adoption_gate'])}</p></section>""")
    fresh = report["corpus_freshness"]
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>每日 Skill 建議採用清單 — {esc(report['report_date'])}</title>
<style>
:root{{--bg:#fbfaf8;--card:#fff;--ink:#1c1b19;--dim:#6b6660;--line:#e4dfd7;--accent:#a94d21;--ok:#2f6b4f;--warn:#936313}}
@media(prefers-color-scheme:dark){{:root{{--bg:#151413;--card:#1e1d1b;--ink:#ece8e2;--dim:#aaa29a;--line:#38332e;--accent:#e18456;--ok:#75b994;--warn:#d5a64c}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;line-height:1.65}}
main{{max-width:1050px;margin:auto;padding:2.2rem 1.2rem 5rem}}a{{color:var(--accent)}}h1{{margin-bottom:.25rem}}h2{{margin-top:2.8rem;border-bottom:1px solid var(--line);padding-bottom:.4rem}}
.muted,.repo{{color:var(--dim);font-size:.88rem}}.notice,.gate{{border-left:3px solid var(--warn);padding:.7rem 1rem;background:var(--card)}}
.grid{{display:grid;gap:.8rem}}@media(min-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}.card{{border:1px solid var(--line);border-radius:10px;padding:1rem 1.1rem;background:var(--card)}}
.card h3{{margin:.5rem 0 0}}.status,.review{{font-size:.72rem;border:1px solid currentColor;border-radius:999px;padding:.12rem .48rem;margin-right:.35rem}}.pilot{{color:var(--ok)}}.watch{{color:var(--warn)}}.review{{color:var(--dim)}}details{{font-size:.86rem}}
</style></head><body><main>
<p><a href="../index.html">← Skills Radar</a></p><h1>每日 Skill 建議採用清單</h1>
<p class="muted">{esc(report['report_date'])} · deterministic daily build</p>
<div class="notice"><strong>{esc(report['status'])}</strong>：{esc(fresh['note'])}<br>財經類只供研究，不授權交易、帳號或 credential 操作。</div>
{''.join(sections)}
<section><h2>證據邊界</h2><p class="muted">master SHA-256: <code>{esc(fresh['master_sha256'])}</code><br>
實際 seed/model: {fresh['actual']['seed']} / {fresh['actual']['model']}；預期: {fresh['expected']['seed']} / {fresh['expected']['model']}。</p>
<p>「沙盒試行」不等於已採用或已上線；repo stars、回測、parser/lint PASS 都不是 EDA 正確性、金融正確性或獲利證明。</p></section>
</main></body></html>"""


def build_report(rows: list[dict], model_report: dict, catalog: dict, reviews: dict,
                 master_path: Path, report_date: str, finance_reviews: dict | None = None,
                 ai_automation_reviews: dict | None = None) -> dict:
    freshness = snapshot_freshness(rows, model_report, master_path)
    catalog_state = catalog_freshness(catalog, freshness)
    categories = {
        "EDA_IC": build_eda(reviews, catalog, freshness),
        "finance-investing": build_finance(rows, freshness, finance_reviews),
        "ai-automation": build_ai_automation(ai_automation_reviews or {}, freshness),
    }
    displayed = []
    for category in categories.values():
        displayed.extend(category.get("recommendations", []))
        displayed.extend(category.get("excluded", []))
    source_review_ready = bool(displayed) and all(
        item.get("source_review", {}).get("status") == "REVIEWED"
        and item.get("source_commit") not in {None, "", "UNKNOWN"}
        for item in displayed
    )
    if freshness["status"] != "CURRENT" or catalog_state["status"] != "CURRENT":
        status = "PREVIEW_STALE_CORPUS"
    elif not source_review_ready:
        status = "PARTIAL_SOURCE_REVIEW"
    else:
        status = "READY_FOR_OWNER_REVIEW"
    return {
        "schema_version": 1,
        "report_date": report_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "corpus_freshness": freshness,
        "asic_catalog_freshness": catalog_state,
        "policy": {
            "states": STATUS_ZH,
            "adopt_requires": "owner approval plus domain runtime proof",
            "finance_boundary": "research only; no trade execution, brokerage/wallet access or credentials",
            "ai_automation_boundary": "public sources and public fixtures only; no private sessions, anti-bot bypass, irreversible actions or confidential engineering data",
            "population_trend_claims": "forbidden in this recommendation artifact",
            "source_review_ready": source_review_ready,
        },
        "categories": categories,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--master", type=Path, default=MASTER)
    parser.add_argument("--output", type=Path, default=OUTPUT_JSON)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    rows = read_rows(args.master)
    report = build_report(
        rows, read_json(MODEL_REPORT, {}), read_json(ASIC_CATALOG, {}),
        read_json(ASIC_REVIEWS, {}), args.master, args.date, read_json(FINANCE_REVIEWS, {}),
        read_json(AI_AUTOMATION_REVIEWS, {}),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    (RESEARCH_DIR / f"{args.date}.md").write_text(render_markdown(report), encoding="utf-8")
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    page = render_html(report)
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / f"{args.date}.html").write_text(page, encoding="utf-8")
    print(
        f"daily recommendations: {args.date}; status={report['status']}; "
        f"EDA={len(report['categories']['EDA_IC']['recommendations'])}; "
        f"finance={len(report['categories']['finance-investing']['recommendations'])}; "
        f"ai-automation={len(report['categories']['ai-automation']['recommendations'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
