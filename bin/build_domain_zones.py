#!/usr/bin/env python3
"""Build separate EDA/IC and investing research zones.

The zone pages are bounded consumers of already validated recommendation and
timescale artifacts.  They never execute third-party skills and never upgrade
source review, parser/lint output, or public examples into EDA/runtime proof or
investment outcomes.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOMMENDATIONS = ROOT / "corpus" / "daily_skill_recommendations.json"
TIMESCALES = ROOT / "data" / "timescale_summaries.json"
HEALTH = ROOT / "data" / "pipeline_health.json"
AI_AUTOMATION_HISTORY = ROOT / "data" / "ai_automation_history.json"
EXPERT_WATCHLIST = ROOT / "data" / "expert_watchlist.json"
OUTPUT = ROOT / "corpus" / "domain_zones.json"

SCALES = ("day", "week", "month", "quarter")
SCALE_ZH = {"day": "日", "week": "週", "month": "月", "quarter": "季"}


def load(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _reviewed(item: dict) -> bool:
    return item.get("source_review", {}).get("status") == "REVIEWED"


def _dedupe(items: list[dict]) -> list[dict]:
    out, seen = [], set()
    for item in items:
        key = (item.get("repo"), item.get("path"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def cycle_views(history: dict, domain: str) -> list[dict]:
    field = "eda_ic_readout" if domain == "EDA_IC" else "finance_readout"
    evidence_key = "E8_eda_ic" if domain == "EDA_IC" else "E9_finance"
    views = []
    for scale in SCALES:
        record = history.get("latest", {}).get(scale)
        if not record or record.get("status") != "AI_GENERATED":
            views.append({"scale": scale, "scale_zh": SCALE_ZH[scale], "status": "MISSING"})
            continue
        ai = record.get("ai", {})
        if domain == "EDA_IC":
            context = {
                "day": "日尺度只決定今天是否有新的 source/review/evidence 需要處理；不因單日件數改寫設計方法。",
                "week": "週尺度用來從 spec、testbench、formal、debug 與 synthesis 缺口中，選一個可逆 canary。",
                "month": "月尺度檢查 automation portfolio 是否真的補到 fixed-point、cycle contract 與證據鏈，而不是累積更多工具名稱。",
                "quarter": "季尺度才適合調整整體架構：哪些契約已跨 block 重用、哪些仍只有公開 source review、哪些需要退役。",
            }[scale]
            counterpoint = (
                "公開 skill 供給很可能低估公司內數位 IC 實務；secondary taxonomy 目前為 "
                f"{record.get('evidence', {}).get(evidence_key, {}).get('taxonomy_validation', 'UNKNOWN')}，"
                "因此候選數與關鍵字命中不能替代人工審查或 NX runtime evidence。"
            )
            actions = {
                "day": ["檢查新候選是否改變 pinned source、license、dependency 或風險；沒有就維持清單。"],
                "week": ["只挑一個公開 toy block canary，留下 design/verification intent 與 exact evidence manifest。"],
                "month": ["檢查 spec→SVA/TB→VCS/Verdi→DC/LEC/ECO 各 gate 是否仍有無人負責的斷點。"],
                "quarter": ["只把跨至少三個 block 可重現的 contract 提升為公司級 skill；其餘維持 experiment。"],
            }[scale]
            falsifiers = ["若實際 canary 無法重現、需要外傳內部資訊或不能產生 tool readback，該 skill 應降級或退役。"]
        else:
            context = {
                "day": "日尺度是一條 research tape：只記錄 reviewed skill、source pin、license 與引用是否改變，不談趨勢。",
                "week": "週尺度檢查研究方法組合是否涵蓋來源、對帳、論點、估值、風險與證偽，而不是追逐熱門名稱。",
                "month": "月尺度適合形成公開半導體／WiFi／EDA 產業 thesis 與 anti-thesis；技術可行性、商業假設與估值必須分開。",
                "quarter": "季尺度回顧哪些 thesis 被推翻、資料如何修訂、敏感度是否漂移，以及第二位讀者能否重算。",
            }[scale]
            counterpoint = "GitHub 上的財經 skill 供給不是機構採用證據；公開資料也會漏掉內部研究。方法品質只能由來源、重算與反證來提升。"
            actions = {
                "day": ["檢查 reviewed source 的 commit/license/reference drift，選一個無 credential 的可逆閱讀或 canary。"],
                "week": ["更新 method portfolio 的 promotion/demotion 與下週必查 falsifier。"],
                "month": ["以公開 filing、transcript、標準與供應鏈交叉驗證 thesis/anti-thesis。"],
                "quarter": ["稽核 citation reachability、公式 readback、資料修訂與第二讀者重現；不用 P&L 當流程品質。"],
            }[scale]
            falsifiers = ["若來源不可達、公式無法重算、as-of/revision 不明或輸出滑向買賣指令，該方法應降級或排除。"]
        views.append({
            "scale": scale,
            "scale_zh": SCALE_ZH[scale],
            "status": "AI_GENERATED",
            "period": record.get("period"),
            "headline": ai.get("headline"),
            "lead": ai.get(field),
            "context": context,
            "counterpoint": counterpoint,
            "next_actions": actions,
            "falsifiers": falsifiers,
            "caveats": ai.get("caveats", [])[:3],
            "confidence": ai.get("confidence"),
            "evidence": record.get("evidence", {}).get(evidence_key, {}),
            "generated_at": record.get("generated_at"),
            "claim_boundary": (
                "AI 觀點受 period evidence 約束；它不是 skill 正確性、EDA signoff、"
                "實際部署或投資績效證明。"
            ),
        })
    return views


def _skills_for_role(items: list[dict], field: str, role: str) -> list[str]:
    return [
        item.get("name") or item.get("path") or "unknown"
        for item in items
        if item.get("recommendation") != "exclude"
        if item.get("owner_dossier", {}).get(field) == role
    ]


def eda_automation_roadmap(items: list[dict]) -> dict:
    role_field = "automation_role"
    stages = [
        {
            "order": 1, "id": "intent", "title": "設計意圖編譯器",
            "skills": _skills_for_role(items, role_field, "design-intent-compiler"),
            "deliverable": "design intent、cycle contract、fixed-point/interface/reset invariants 與 acceptance boundary。",
            "owner_gate": "owner 核准行為與可變動空間後才允許生成候選 RTL。",
            "proof": "spec/cycle table readback；尚不是 RTL 功能 PASS。",
        },
        {
            "order": 2, "id": "tb", "title": "Verification contract factory",
            "skills": _skills_for_role(items, role_field, "testbench-contract-adapter"),
            "deliverable": "stimulus space、bounded wait、scoreboard、reset/backpressure、coverage exit gate。",
            "owner_gate": "重寫進既有 framework；不匯入第三方 helper 或 build layout。",
            "proof": "VCS compile/sim、seed manifest、mismatch log 與 coverage readback。",
        },
        {
            "order": 3, "id": "formal", "title": "Spec-linked property factory",
            "skills": _skills_for_role(items, role_field, "spec-linked-property-candidate"),
            "deliverable": "每條 candidate property 對應 requirement，分開 assume/assert/cover。",
            "owner_gate": "AI 只提案；assumption、fairness 與 completeness 由 owner/formal owner 決定。",
            "proof": "正式 proof result、vacuity 與 counterexample review。",
        },
        {
            "order": 4, "id": "debug", "title": "VCS／Verdi 證據萃取器",
            "skills": _skills_for_role(items, role_field, "simulation-evidence-extractor"),
            "deliverable": "可重跑的 FSDB event/coverage query 與 bounded JSON evidence。",
            "owner_gate": "只讀既有 run artifact，不外傳內部 signal、license 或 waveform。",
            "proof": "同一 clock edge sampling、API readback、compile/sim status 與 denominator。",
        },
        {
            "order": 5, "id": "synthesis", "title": "Synthesis／LEC／ECO claim governor",
            "skills": _skills_for_role(items, role_field, "synthesis-evidence-governor"),
            "deliverable": "RTL/filelist/tool/library/constraint manifest；lint、DC、LEC 與前端 ECO claims 分層。",
            "owner_gate": "library、constraint、ECO boundary、threshold 與 waiver 只取自 internal golden flow；不延伸到 P&R/physical signoff。",
            "proof": "真實 DC／Formality/LEC／ECO report readback；各 gate 不互相替代。",
        },
        {
            "order": 6, "id": "learn", "title": "Evidence-backed learning loop",
            "skills": [],
            "deliverable": "只回流獲准的 manifest、claim、失敗模式與通用方法，形成跨 block 可複用資產。",
            "owner_gate": "公司內容不進 public repo；promotion 必須保留 realm、authority 與 freshness。",
            "proof": "另一個 agent 可由 checkpoint 重現 exact next action，不需 owner 重講上下文。",
        },
    ]
    return {
        "thesis": (
            "對 WiFi baseband ASIC，先自動化意圖與證據，再自動化 RTL mutation。"
            "最有價值的不是把第三方 skill 整包裝進公司環境，而是抽出可審查契約，"
            "由 OA 產 deterministic bundle、NX 跑真實 EDA、證據回流後才升級 claim。"
        ),
        "nx_context": "SNAPSHOT_ONLY",
        "stages": stages,
        "first_90_day_focus": [
            "零到三十天：建立 intent schema、evidence manifest 與非機密 ready/valid canary。",
            "三十一到六十天：接 VCS compile/elaborate/sim 與只讀 Verdi/FSDB evidence。",
            "六十一到九十天：接 DC、Formality/LEC 與前端 ECO evidence；自動改 RTL 保留在最後。",
        ],
        "internal_skill_suite": [
            "wifi-bbdd-intent-compiler", "fixed-point-bittrue-contract", "rtl-artifact-generator",
            "spec-bound-sva-generator", "vcs-evidence-runner", "verdi-fsdb-analysis",
            "synthesis-lec-eco-evidence", "claim-boundary-auditor",
        ],
        "cadence_contract": {
            "day": "source/review/evidence drift tape; no trend claim",
            "week": "one reversible canary selected from the largest evidence gap",
            "month": "spec-to-signoff capability coverage and repeated failure patterns",
            "quarter": "cross-block reuse, retirement and operating-model decisions",
        },
    }


def finance_research_roadmap(items: list[dict]) -> dict:
    roles = [
        ("market-data-provenance", "來源與資料版本", "時間戳、revision、corporate action、缺值與 readback。"),
        ("research-data-control", "資料品質與對帳", "單位、期間、currency、公式與跨表一致性。"),
        ("thesis-and-disconfirmation", "論點與反證", "主張、證據、反方材料、待查問題分離。"),
        ("reproducible-valuation", "可重算估值", "假設、公式、敏感度與來源逐層展開。"),
        ("risk-and-counterevidence", "風險與異常", "red flag 只形成查證問題，不直接定性。"),
        ("hypothesis-falsification", "回測證偽", "樣本外、成本、leakage、survivorship 與 benchmark。"),
    ]
    return {
        "thesis": "投資專區只建立可追溯、可重算、可被反駁的研究流程；不連帳戶、不下單、不把模型分數變成方向指令。",
        "stages": [
            {
                "order": i + 1, "id": role, "title": title, "deliverable": deliverable,
                "skills": _skills_for_role(items, "research_role", role),
                "proof": "一手來源、公式/readback、反方證據與第二位讀者重算。",
            }
            for i, (role, title, deliverable) in enumerate(roles)
        ],
        "cadence_contract": {
            "day": "reviewed skill/source drift and one reversible reading canary",
            "week": "method portfolio coverage, promotions/demotions and falsifiers",
            "month": "public semiconductor/WiFi/EDA thesis and anti-thesis notebook",
            "quarter": "research operating-system calibration and reproducibility review",
        },
    }


def ai_automation_cycles(ai_history: dict, category: dict, report_date: str) -> list[dict]:
    observations = ai_history.get("observations", [])
    latest = ai_history.get("latest") or (observations[-1] if observations else {})
    thesis = category.get("strategic_thesis", {})
    run = date.fromisoformat(report_date)
    iso_year, iso_week, _ = run.isocalendar()
    period_ids = {
        "day": report_date,
        "week": f"{iso_year}-W{iso_week:02d}",
        "month": run.strftime("%Y-%m"),
        "quarter": f"{run.year}-Q{((run.month - 1) // 3) + 1}",
    }
    thresholds = {"day": 1, "week": 3, "month": 10, "quarter": 30}
    horizons = {
        "day": (
            thesis.get("headline") or "今日先建立可稽核基線",
            "日尺度只處理 source pin、健康狀態、依賴與風險是否改變；單日星數不構成趨勢。",
            ["檢查 pinned source、license、credential surface 與 doctor/readback 是否漂移。"],
        ),
        "week": (
            "從工具清單轉向一條可失敗、可恢復的 harness canary",
            "週尺度應選一個角色缺口做公開 fixture 實驗，量測重試、rollback、context retention 與 owner interruption。",
            ["只挑一條端到端 canary，留下 before/after trace、checkpoint 與 failure taxonomy。"],
        ),
        "month": (
            "檢查控制平面是否形成，而不是又累積一批 framework",
            "月尺度看 reach、context、state、tool、eval 與 sandbox 是否有明確接口；沒有 evidence contract 的整合應降級。",
            ["淘汰重疊元件，保留能產生 artifact readback、負向測試與可替換 adapter 的組合。"],
        ),
        "quarter": (
            "把專精押在 Evidence-Governed Domain Agent Harness",
            "季尺度才判斷這套方法是否跨多個高風險工程任務重現，並能抽象成不含機密的產品化能力。",
            ["只有跨至少三種任務重現 attention saving 與 evidence integrity，才升格為可複用平台。"],
        ),
    }
    views = []
    for scale in SCALES:
        count = len(observations)
        enough = count >= thresholds[scale] and latest.get("date") == report_date
        headline, context, actions = horizons[scale]
        if not enough and scale != "day":
            headline = f"{SCALE_ZH[scale]}尺度歷史尚短，先保留觀測而不宣稱趨勢"
        views.append({
            "scale": scale, "scale_zh": SCALE_ZH[scale],
            "status": "AI_GENERATED" if enough else "INSUFFICIENT_HISTORY",
            "period": {"scale": scale, "period_id": period_ids[scale]},
            "headline": headline,
            "lead": thesis.get("claim") or "目前只有初始觀察。",
            "context": context,
            "counterpoint": thesis.get("counterpoint") or "公開專案供給不等於實際採用。",
            "next_actions": actions,
            "falsifiers": thesis.get("falsifiers", [])[:4],
            "confidence": thesis.get("confidence", "LOW") if enough else "LOW",
            "evidence": {
                "history_started_at": ai_history.get("started_at"),
                "observation_days": count,
                "review_count": latest.get("review_count"),
                "grade_counts": latest.get("grade_counts", {}),
                "role_counts": latest.get("role_counts", {}),
                "source_drift_repos": latest.get("change_since_previous", {}).get("source_drift_repos", []),
            },
            "claim_boundary": thesis.get("history_boundary") or (
                "此專區沒有足夠的逐日歷史，不把 cross-sectional review 寫成時間趨勢。"
            ),
        })
    return views


def github_breakout_lab(items: list[dict], ai_history: dict) -> dict:
    """Treat stars as a useful attention signal without upgrading them to proof."""
    latest = ai_history.get("latest", {})
    metrics = {item.get("repo"): item for item in latest.get("repo_metrics", [])}
    star_delta = latest.get("change_since_previous", {}).get("star_delta", {})
    ranked = []
    for item in items:
        fact = metrics.get(item.get("repo"), {})
        stars = fact.get("stars")
        if not isinstance(stars, int):
            stars = item.get("stars_snapshot")
        grade = item.get("source_review", {}).get("grade")
        if isinstance(stars, int) and stars >= 50_000:
            bucket = "OUTLIER_ATTENTION"
        elif isinstance(stars, int) and stars >= 10_000:
            bucket = "BREAKOUT_SCALE"
        elif grade == "A":
            bucket = "QUIET_HIGH_SIGNAL"
        else:
            bucket = "EMERGING_OR_NICHE"
        ranked.append({
            "name": item.get("name"), "repo": item.get("repo"), "stars": stars,
            "star_delta": star_delta.get(item.get("repo")), "bucket": bucket,
            "grade": grade, "recommendation": item.get("recommendation"),
            "commit_drift": fact.get("commit_drift"), "pushed_at": fact.get("pushed_at"),
            "implementation_fit": item.get("owner_dossier", {}).get("personalized_fit"),
            "first_experiment": item.get("owner_dossier", {}).get("first_experiment"),
        })
    ranked.sort(key=lambda row: (-(row.get("stars") or -1), row.get("repo") or ""))
    history_days = len(ai_history.get("observations", []))
    return {
        "status": "COMPARABLE" if history_days >= 2 else "BASELINE_ONLY",
        "history_days": history_days,
        "thesis": (
            "Stars 是稀缺注意力與出圈程度的強訊號：用來決定先拆誰；"
            "source review、release/commit、failure model、tests 與 canary 才決定學什麼、能否採用。"
        ),
        "ranked": ranked,
        "lenses": [
            "Reach：star level、star velocity、fork／contributor／release activity；辨認已出圈與正在加速的項目。",
            "Implementation：state model、adapter boundary、failure/retry、test topology、artifact schema 與 negative cases。",
            "Transfer：哪些方法可改編成 IC intent、EDA evidence、debug replay、verification factory；哪些只是 web/SaaS 假設。",
            "Durability：模型原生能力若吸收功能後，domain schema、oracle、evidence、permission 與 recovery 是否仍有價值。",
        ],
        "velocity_boundary": (
            "目前 observation tape 只有一個真實日快照，不能計算可靠 star velocity；"
            "第二個完整日後才顯示 delta，週/月尺度再判斷 breakout。"
        ),
        "quiet_signal_rule": (
            "保留 grade A 但 stars 尚低的 quiet high-signal 專案；它們可能比熱門 framework 更接近工程方法論。"
        ),
    }


def expert_methodology_desk(watchlist: dict) -> dict:
    tracks = {item.get("id"): item for item in watchlist.get("tracks", [])}
    grouped = []
    for track_id, track in tracks.items():
        grouped.append({
            **track,
            "experts": [item for item in watchlist.get("experts", []) if item.get("track") == track_id],
        })
    return {
        "status": watchlist.get("status", "MISSING"),
        "source_status": watchlist.get("source_status", {}),
        "tracks": grouped,
        "reddit": watchlist.get("reddit", []),
        "daily_card_contract": watchlist.get("daily_card_contract", []),
        "deployment_brief_contract": watchlist.get("deployment_brief_contract", {}),
        "cadence": [
            "日：只記本人新貼文／原始 repo、method delta、反證與一個 IC translation；沒有新文就不硬寫。",
            "週：將貼文聚成 model、agent harness、coding、systems、AI hardware/EDA thesis，找共識與矛盾。",
            "月：選一個方法做 public reproducible canary；只有 code/paper/tool evidence 才能 promotion。",
            "季：淘汰只剩人物聲量的主題，保留跨來源、跨任務重現的工程方法。",
        ],
        "claim_boundary": watchlist.get("claim_boundary"),
    }


def ai_automation_roadmap(items: list[dict], thesis: dict) -> dict:
    by_role = {}
    for item in items:
        by_role.setdefault(item.get("owner_fit"), []).append(item.get("name"))
    return {
        "thesis": thesis.get("owner_specialization") or (
            "建立 evidence-governed domain agent harness，而不是通用 prompt 或爬蟲集合。"
        ),
        "stages": [
            {"order": 1, "title": "Evidence kernel 與 change governance",
             "deliverable": "先定義 task、intent、approval、failure、artifact 與 claim boundary，再選 framework。",
             "skills": by_role.get("harness-governance", []),
             "proof": "change manifest、failure taxonomy、owner disposition 與 rollback readback"},
            {"order": 2, "title": "Public intake 與 typed tool registry",
             "deliverable": "公開來源 adapter 具備 capability probe、ordered fallback、allowlist 與 provenance。",
             "skills": by_role.get("reach-routing", []) + by_role.get("tool-discovery", []),
             "proof": "active backend、scope、negative authorization 與 source provenance"},
            {"order": 3, "title": "Durable state 與 reversible context",
             "deliverable": "讓長任務能中斷續跑，並讓壓縮後的原始證據可按需取回。",
             "skills": by_role.get("durable-orchestration", []) + by_role.get("context-compression", []),
             "proof": "checkpoint conformance、idempotence、uncompressed holdout 與 retrieval trace"},
            {"order": 4, "title": "Evaluation rail 與最小權限執行",
             "deliverable": "trace 連回 oracle，sandbox 明確限制網路、檔案、credential 與 artifact。",
             "skills": by_role.get("observability-evaluation", []) + by_role.get("sandbox", []),
             "proof": "sanitized trace、eval linkage、policy readback 與 isolation negative test"},
            {"order": 5, "title": "ASIC automation domain adapter",
             "deliverable": "把設計意圖與驗證意圖編譯成確定性 bundle，工網只跑既有 EDA flow 並回傳證據。",
             "skills": [],
             "proof": "公開 toy RTL 先過 canary；內部 claim 只接受核准環境的真實工具證據"},
        ],
        "first_90_day_focus": [
            "前一個月：完成 evidence kernel、tool registry、checkpoint 與負向權限測試。",
            "第二個月：在公開 toy RTL 串起 intent→candidate artifact→sim/formal evidence 的可恢復流程。",
            "第三個月：用核准的 deterministic bundle 接現有工具；量測失敗重現時間、owner 介入與證據完整性。",
        ],
        "internal_skill_suite": [
            "intent-compiler", "tool-capability-registry", "durable-run-governor",
            "evidence-extractor", "claim-auditor", "sandbox-policy-checker",
        ],
        "cadence_contract": {
            "day": "source drift, security boundary and one reversible next action",
            "week": "one end-to-end canary and failure/recovery evidence",
            "month": "portfolio overlap, missing interfaces and promotion/demotion",
            "quarter": "cross-task reuse, attention saving and productizable abstraction",
        },
    }


def ai_automation_analysis_plan(thesis: dict) -> dict:
    """Owner-facing research desk contract across four evidence horizons."""
    return {
        "objective": (
            "把公開 skill 供給、pinned source review 與每日 observation tape 轉成可證偽的決策情報，"
            "並只把能改善 WiFi baseband ASIC 前端設計、驗證、合成或前端 ECO 的方法送入 canary。"
        ),
        "decision_rule": (
            "先看痛點與角色缺口，再看 evidence maturity、權限邊界與可逆性；stars 只作注意力訊號，"
            "不能單獨升格為採用、可靠性或市場需求證據。"
        ),
        "horizons": [
            {
                "scale": "day", "scale_zh": "日",
                "question": "今天有哪些 source、license、依賴、credential surface 或安全邊界漂移？",
                "inputs": "pinned commit、daily metadata、doctor/readback、change_since_previous",
                "method": "逐 repo diff；只記新事實、反證與一個可逆 next action",
                "deliverable": "一張 observation card 與 ADOPT／PILOT／WATCH／REJECT 變更",
                "work_translation": "避免把漂移的工具或登入型 adapter 帶進 ASIC automation。",
                "claim_boundary": "單日 stars、commit 數與社群聲量不是趨勢或採用率。",
            },
            {
                "scale": "week", "scale_zh": "週",
                "question": "哪個 harness 角色缺口值得用一條端到端 canary 驗證？",
                "inputs": "七角色 coverage、failure taxonomy、checkpoint、owner interruption、rollback trace",
                "method": "只選一條公開 fixture；比較 before/after failure recovery 與證據完整性",
                "deliverable": "一份可重跑 canary、負向測試、淘汰條件與 promotion decision",
                "work_translation": "優先驗證 spec→intent→RTL/SVA→sim evidence 的可恢復交接。",
                "claim_boundary": "公開 toy PASS 不能升格為 VCS、Verdi、DC、Formality/LEC 或產品 RTL PASS。",
            },
            {
                "scale": "month", "scale_zh": "月",
                "question": "哪些看似分散的 skills 正收斂成控制平面，哪裡仍有稀缺而高痛的空白？",
                "inputs": "角色 coverage、promotions/demotions、跨 repo interface、失敗重現時間、重疊成本",
                "method": "建立 thesis／anti-thesis；淘汰重疊 framework，追蹤可替換 schema 與 evidence contract",
                "deliverable": "利基地圖、portfolio cut、下一個月的單一能力投資主題",
                "work_translation": "把通用 pattern 收斂成 intent、tool evidence、debug handoff 與 ECO audit 元件。",
                "claim_boundary": "供給缺口只是假設；沒有真實使用痛點與 canary，不是市場機會。",
            },
            {
                "scale": "quarter", "scale_zh": "季",
                "question": "同一 evidence contract 是否跨三類高風險任務重現，值得成為你的專業護城河？",
                "inputs": "跨任務 reproducibility、owner interruption、recovery effort、evidence integrity、外部需求訊號",
                "method": "做平台校準與產品化審查；要求可攜 state、可替換 worker 與 realm boundary",
                "deliverable": "專精押注、停止項目、下一季 build/buy/learn 決策與產品化假設",
                "work_translation": "評估 Evidence-Governed Domain Agent Harness 是否成為 ASIC automation 核心能力。",
                "claim_boundary": "內部效率或 demo 不等於付費需求；EDA claim 仍需核准環境真工具證據。",
            },
        ],
        "niche_filters": [
            "高頻或高代價工程痛點，但公開 skill 供給稀疏",
            "模型能力提升後仍需要的 domain schema、oracle、evidence 與 approval",
            "可先用公開 fixture 驗證，之後以 deterministic bundle 進核准環境",
            "能降低失敗重現時間、重複脈絡說明或 owner interruption，且不犧牲 verification integrity",
        ],
        "priority_hypotheses": [
            {
                "name": "RTL／DV Evidence Kernel",
                "why": "把 requirement、cycle contract、assertion、simulation artifact、review claim 與 owner disposition 串成同一 ledger。",
                "first_canary": "公開 toy datapath 的 intent→RTL/SVA→simulation evidence bundle 與獨立 claim audit。",
                "promotion_gate": "另一個 worker 可只靠 bundle 重現，且 false-PASS negative test 能被 gate 擋下。",
            },
            {
                "name": "EDA Tool Capability Registry",
                "why": "把 VCS、Verdi、lint、CDC、synthesis、LEC/ECO 的 capability、preflight、版本與失敗原因型別化。",
                "first_canary": "先用 mock adapter 驗證 allowlist、negative authorization、artifact manifest 與 fallback，不連公司工具。",
                "promotion_gate": "進核准環境後，真實 tool/version/command/report readback 能對上相同 schema。",
            },
            {
                "name": "Frontend ECO Failure Replay",
                "why": "前端 ECO 的稀缺價值不是自動改 RTL，而是保存 root cause、變更邊界、等價性預期與 rollback 證據。",
                "first_canary": "公開 combinational/sequential toy change 的 before/after cone、test、equivalence expectation 與 rollback trace。",
                "promotion_gate": "無 owner approval 不改 source；沒有 LEC/正式等價性 readback 不宣稱 ECO 正確。",
            },
        ],
        "workbench": {
            "production": "deterministic Python builders、versioned JSON evidence、tests 與 Pages readback",
            "exploration": "Jupyter notebook 僅用於 cohort、trend、niche hypothesis 與圖表探索；結論須回寫受測試的 pipeline",
            "ai_role": "AI 撰寫 thesis／anti-thesis 與決策敘事，但不能覆寫 evidence ledger 或工具結果",
            "nx_context": "SNAPSHOT_ONLY",
        },
        "thesis": thesis.get("potential_track") or "Evidence-Governed Domain Agent Harness",
    }


def ic_design_automation_blueprint() -> dict:
    """Public, sanitized build plan for an evidence-governed IC automation stack.

    The blueprint deliberately describes contracts, artifacts and gates rather
    than company tool commands or design details.  Real EDA adapters remain an
    owner-approved NX experiment and cannot be proven by this public page.
    """
    return {
        "status": "PROPOSED_REQUIRES_OWNER_APPROVAL",
        "context": "OA_CONTEXT=PARTIAL · NX_CONTEXT=SNAPSHOT_ONLY",
        "north_star": (
            "把每次 IC 設計變更壓成可恢復的 intent→execution→evidence→decision loop；"
            "工程師只需要看變更邊界、最早可信失敗與真正需要裁定的問題。"
        ),
        "principles": [
            "先建 evidence kernel，再考慮自動產生或修改 RTL。",
            "AI 可提出 candidate；只有 deterministic gate 與真實工具 readback 能提升 claim。",
            "最快的迭代不是少跑驗證，而是更早得到可定位、可重播的失敗。",
            "把 owner attention 當受限資源，但不得靠隱藏風險或降低 verification integrity 節省。",
        ],
        "layers": [
            {
                "id": "environment", "title": "1. 可重現環境底座",
                "goal": "任何核准 worker 都能從乾淨 checkout，以單一入口重現同一個 stage。",
                "build": [
                    "repo-owned control plane；流程狀態不只存在 agent 對話",
                    "tool capability registry：版本、license/preflight、輸入輸出、side effect、timeout 與 fallback",
                    "content-addressed artifact store、固定 seed、相對路徑、原子寫入、idempotent rerun",
                ],
                "artifacts": ["tool_capabilities.json", "run_manifest.json", "environment_readback.json"],
                "proof": "clean-checkout replay、版本/readback 相符、缺工具或權限時 fail closed",
                "attention": "工程師不再反覆追問『跑的是哪一版、哪個工具、哪個目錄』。",
                "skills": ["MCP Reference Servers", "LangGraph", "Agentic Harness Engineering"],
            },
            {
                "id": "iteration", "title": "2. 加速迭代與失敗重播",
                "goal": "每次變更先跑最便宜且足以推翻 claim 的 gate，再逐級升級。",
                "build": [
                    "diff impact map：變更 requirement/module/interface/assertion 對應受影響測試與 EDA stage",
                    "fast/medium/signoff 三速 queue、checkpoint/resume、cache validity 與 duplicate-run suppression",
                    "保存 first failing seed、最早 divergence、輸入版本、工具版本與最小 replay command",
                ],
                "artifacts": ["impact_map.json", "gate_plan.json", "failure_replay.json"],
                "proof": "另一個 worker 可重現同一最早失敗；cache miss/hit 理由可讀回",
                "attention": "把『重跑整包再看海量 log』改成『先看最小失敗與受影響 cone』。",
                "skills": ["LangGraph", "systemverilog-waveform-debug", "rtl-equivalence-checker"],
            },
            {
                "id": "accuracy", "title": "3. 準確度與 false-PASS 防線",
                "goal": "準確度先定義成 claim 可追溯、oracle 可重現、弱 gate 不冒充強 gate。",
                "build": [
                    "design intent／verification intent schema：width、signedness、fixed-point、cycle、reset、protocol、non-goal",
                    "requirement→assertion/test/coverage/evidence traceability；每個 UNKNOWN 保留 owner/next check",
                    "negative fixture、mutation、vacuity、X/unknown、boundary 與 stale-golden 檢查",
                ],
                "artifacts": ["design_intent.yaml", "verification_intent.yaml", "claim_ledger.jsonl"],
                "proof": "故意植入的 false PASS 能被擋下；每個 PASS 可回到 oracle、輸入、版本與 exact gate",
                "attention": "工程師不用重讀整份報告，只審未證實假設、衝突與 promotion decision。",
                "skills": ["spec-planner", "rtl-p3-uarch-policy", "rtl-quality-reviewer"],
            },
            {
                "id": "attention", "title": "4. 認知負載與 owner decision surface",
                "goal": "每次只呈現三件事：改了什麼、最早可信失敗在哪、哪個問題必須由 owner 決定。",
                "build": [
                    "resumable checkpoint：intent、assumption、evidence、failure、decision、exact next action",
                    "相同結果自動折疊；新風險、authority conflict、irreversible action 才打斷 owner",
                    "把零散問題批次化成 recommendation／alternatives／consequences／default decision packet",
                ],
                "artifacts": ["checkpoint.json", "decision_packet.md", "owner_disposition.json"],
                "proof": "handoff 不需重講背景；可量測 interruption、重複提問、恢復工時與 owner correction",
                "attention": "AI 承接記憶與可逆執行，人保留高價值架構判斷與不可逆裁定。",
                "skills": ["Agentic Harness Engineering", "Headroom", "Langfuse"],
            },
            {
                "id": "eda", "title": "5. EDA 方法論與 typed evidence adapter",
                "goal": "每個 EDA stage 只回答自己有權回答的問題，輸出 typed evidence 而非自然語言 PASS。",
                "build": [
                    "adapter 共通 contract：tool/version/command/input hash/corner/seed/status/report hash/line/quote",
                    "lint、compile/elaboration、simulation、CDC/RDC、formal、synthesis、LEC 分開建 authority 與失敗型別",
                    "先做 mock/conformance adapter；進 NX 後再用核准報告校準 parser 與 negative fixture",
                ],
                "artifacts": ["eda_capabilities.json", "evidence_manifest.json", "gate_result.json"],
                "proof": "unknown format、空報告、零 compared points、缺 corner/version 或 parser ambiguity 一律不升級 claim",
                "attention": "把不同工具 log 統一成可排序 failure taxonomy，但保留原始 report provenance。",
                "skills": ["review-rtl-architecture", "hw-cdc", "prepare-rtl-for-synth", "equivalence-check"],
            },
            {
                "id": "verification", "title": "6. Verification factory",
                "goal": "把單點 testbench 經驗轉成可跨 block 重用的 oracle、observer、assertion、coverage 與 replay pattern。",
                "build": [
                    "Reference Model 是 expected 唯一來源；Scoreboard 只負責配對與 bit-true compare",
                    "cycle/reset/valid-ready/backpressure contract 加上多節點 observer，找 earliest divergence",
                    "directed boundary、constrained-random、assertion/formal、coverage hole、ECO equivalence 各自有 exit gate",
                ],
                "artifacts": ["verification_plan.yaml", "traceability_matrix.json", "coverage_ledger.json"],
                "proof": "正常、邊界、故障注入與 stale/misaligned oracle 都能得到預期 verdict；重跑結果一致",
                "attention": "debug 從『最後輸出錯了』縮成『哪個 contract、哪個節點、哪個 cycle 首次偏離』。",
                "skills": ["formal-verification", "systemverilog-waveform-debug", "equivalence-check"],
            },
        ],
        "iteration_ladder": [
            {"tier": "G0 · Intake/Preflight", "when": "每次 task／環境變更",
             "gates": "intent/schema、source pin、tool capability、permission、golden/version readback",
             "stop": "輸入不完整、authority 衝突、tool/version 不符就停止。"},
            {"tier": "G1 · Fast structural", "when": "每次 RTL／TB candidate diff",
             "gates": "format/parser、compile/elaboration、lint、width/signedness/X/reset 靜態檢查",
             "stop": "只證明結構 gate；不得寫成功能 PASS。"},
            {"tier": "G2 · Block behavior", "when": "G1 通過後",
             "gates": "directed smoke、bit-true oracle、cycle assertions、boundary/mutation negative tests",
             "stop": "先保留 first failure；不要用後續大量錯誤淹沒 root cause。"},
            {"tier": "G3 · Regression/debug", "when": "checkpoint／合併前",
             "gates": "impact-selected regression、fixed seeds、multi-node earliest divergence、coverage holes",
             "stop": "coverage 數字缺 denominator 或 waiver 無 owner disposition，不能 closure。"},
            {"tier": "G4 · Structural proof", "when": "跨 clock/reset、控制協定或高風險變更",
             "gates": "CDC/RDC、SVA/formal、assumption/vacuity、counterexample replay",
             "stop": "inconclusive、vacuous、unreachable 與 proven 必須分開。"},
            {"tier": "G5 · Synthesis/ECO promotion", "when": "RTL frozen／frontend ECO",
             "gates": "synthesis report、constraint/corner readback、LEC substance、rollback bundle",
             "stop": "沒有 compared points、unproven points=0 與真實 report readback，不宣稱 equivalence。"},
            {"tier": "G6 · Owner disposition", "when": "任何 sign-off 或 source mutation 前",
             "gates": "Claim／Evidence／Risk、waiver、residual risk、owner accept/reject/defer/verify",
             "stop": "AI narrative、unit test 或 parser PASS 永不自動升格 sign-off。"},
        ],
        "verification_patterns": [
            {"priority": "P0", "name": "Contract-to-check traceability",
             "pattern": "每個 requirement 綁定 assertion/test/coverage/oracle/evidence；未綁定即 UNKNOWN。",
             "catches": "漏驗需求、文件與 RTL 認知漂移、沒有證據的 satisfied claim。"},
            {"priority": "P0", "name": "Reference Model／Scoreboard 分責",
             "pattern": "Reference Model 唯一產生 expected；Scoreboard 只做 transaction pairing 與 bit-true compare。",
             "catches": "oracle 與 checker 同錯、scoreboard 隱藏計算、debug 無法判斷誰錯。"},
            {"priority": "P0", "name": "Cycle／Reset／Protocol contract",
             "pattern": "明列 latency、valid-ready、bubble/backpressure、reset window、flush 與例外；用 assertion 執行化。",
             "catches": "off-by-one、reset race、gap 才出現的錯位、吞吐與資料配對錯誤。"},
            {"priority": "P0", "name": "Multi-observer earliest divergence",
             "pattern": "在高資訊量中間節點保存 act/exp 與 cycle metadata，先找第一個可信偏離。",
             "catches": "只看到最終 mismatch、波形 probe 無界擴張、跨 pipeline 猜 root cause。"},
            {"priority": "P0", "name": "False-PASS mutation test",
             "pattern": "故意破壞 width、signedness、latency、reset、golden freshness 或 compared-points，確認 gate 會失敗。",
             "catches": "checker 沒接上、vacuous property、空報告 PASS、stale golden 與弱 gate 冒充強 gate。"},
            {"priority": "P1", "name": "Atomic transaction-field alignment",
             "pattern": "transaction、driver、monitor、sequence、reference input schema 視為同一原子變更並做欄位 diff。",
             "catches": "欄位漏抄造成 X-taint、driver/monitor semantic drift、可跑但答案錯。"},
            {"priority": "P1", "name": "Golden provenance and differential oracle",
             "pattern": "golden 綁 source/version/parameter/seed/hash；必要時以兩個獨立 oracle 做 differential check。",
             "catches": "不同批次 golden 混用、reference 版本漂移、模型與 RTL 同源錯誤。"},
            {"priority": "P1", "name": "Formal assumption／vacuity audit",
             "pattern": "assert/assume/cover 分離，保存 PROVEN/CEX/VACUOUS/INCONCLUSIVE/UNREACHABLE。",
             "catches": "過度 constraint、property 根本未觸發、bounded proof 被誤稱完整。"},
            {"priority": "P1", "name": "Coverage with denominator and holes",
             "pattern": "coverage 必帶 scope、denominator、unreachable/waiver、對應 requirement 與未覆蓋樣本。",
             "catches": "漂亮百分比掩蓋沒採到的功能、coverage closure 無需求語意。"},
            {"priority": "P0", "name": "ECO equivalence plus rollback",
             "pattern": "保存 before/after cone、intent、LEC compared/unproven points、simulation delta 與可回退版本。",
             "catches": "heuristic diff 被誤稱等價、ECO 修 A 壞 B、無法重播或回退。"},
        ],
        "mvp": [
            {"phase": "0–30 天 · Control plane", "build": "intent schema、capability registry、run/evidence manifest、mock adapters、owner decision packet",
             "exit": "公開 toy task 可 clean-checkout 重跑；缺工具/權限/證據會 fail closed。"},
            {"phase": "31–60 天 · Verification kernel", "build": "toy fixed-point datapath、Reference Model/Scoreboard、cycle/reset assertions、multi-observer、五種 mutation",
             "exit": "每種故障都得到預期 verdict，另一個 worker 可重現 earliest divergence。"},
            {"phase": "61–90 天 · NX adapter canary", "build": "經 owner 核准後，只接一條真實 compile/sim/report readback；再評估 CDC/formal/synthesis/LEC",
             "exit": "tool/version/command/input/report hash 可對帳；沒有真 EDA evidence 就停在 experiment。"},
        ],
        "metrics": [
            "time-to-first-trustworthy-failure，而非單純 job wall time",
            "clean-checkout replay success 與 failure reproduction success",
            "false-PASS mutations caught／total injected",
            "requirement-to-evidence completeness 與 UNKNOWN aging",
            "owner interruptions、重複 context requests、handoff recovery effort",
            "waiver 數、vacuous/inconclusive proof 數與未關閉 coverage holes",
        ],
        "reuse_ledger": [
            {"candidate": "intent／manifest／finding／evidence contracts", "decision": "REUSE_AS_IS", "boundary": "只重用 schema 與 fail-closed semantics"},
            {"candidate": "spec→schema→generated verification artifact", "decision": "ADAPT", "boundary": "公開抽象；內部來源與路徑不得外流"},
            {"candidate": "Reference Model、Scoreboard、multi-observer patterns", "decision": "ADAPT", "boundary": "每個 block 重新綁 cycle、golden 與 coverage contract"},
            {"candidate": "typed VCS/Verdi/DC/LEC evidence adapters", "decision": "NEW_EXPERIMENT", "boundary": "需核准 NX canary 與真實 report golden fixtures"},
            {"candidate": "autonomous RTL repair／sign-off", "decision": "BLOCKED_FOR_EVIDENCE", "boundary": "無 owner approval、negative tests、sim/formal/LEC 證據不得啟用"},
        ],
        "owner_decision": {
            "recommendation": "第一個 MVP 選 RTL／DV Evidence Kernel，先完成公開 toy datapath 的五種 false-PASS mutation 與 replay bundle。",
            "alternative": "若先做 tool registry，環境治理更快，但短期無法證明 verification value。",
            "default_if_deferred": "維持公開 blueprint 與 mock adapter，不進 NX、不改任何產品 RTL。",
            "requires_owner_approval": True,
        },
    }


def build_report(recommendations: dict, history: dict, health: dict, report_date: str,
                 ai_history: dict | None = None, expert_watchlist: dict | None = None) -> dict:
    ai_history = ai_history or {}
    expert_watchlist = expert_watchlist or {}
    categories = recommendations.get("categories", {})
    eda_category = categories.get("EDA_IC", {})
    finance_category = categories.get("finance-investing", {})
    ai_category = categories.get("ai-automation", {})
    eda_items = _dedupe(eda_category.get("all_reviewed") or (
        eda_category.get("recommendations", []) + eda_category.get("excluded", [])
    ))
    finance_items = _dedupe(
        finance_category.get("recommendations", []) + finance_category.get("excluded", [])
    )
    ai_items = _dedupe(ai_category.get("all_reviewed") or (
        ai_category.get("recommendations", []) + ai_category.get("excluded", [])
    ))
    eda_cycles = cycle_views(history, "EDA_IC")
    finance_cycles = cycle_views(history, "finance-investing")
    ai_cycles = ai_automation_cycles(ai_history, ai_category, report_date)
    complete = all(x.get("status") == "AI_GENERATED" for x in eda_cycles + finance_cycles)
    current = (
        recommendations.get("status") == "READY_FOR_OWNER_REVIEW"
        and recommendations.get("corpus_freshness", {}).get("status") == "CURRENT"
    )
    ai_required = bool(ai_category)
    review_items = eda_items + finance_items + (ai_items if ai_required else [])
    review_complete = bool(eda_items and finance_items) and (not ai_required or bool(ai_items)) and all(
        _reviewed(item) and item.get("source_commit") not in {None, "", "UNKNOWN"}
        for item in review_items
    )
    ai_history_current = not ai_required or ai_history.get("latest", {}).get("date") == report_date
    status = (
        "READY_FOR_OWNER_REVIEW"
        if current and complete and review_complete and ai_history_current else "PARTIAL"
    )
    execution_context = os.environ.get(
        "SKILLS_RADAR_RUN_CONTEXT",
        health.get("schedule_contract", {}).get("execution_context", "UNKNOWN"),
    )
    return {
        "schema_version": 1,
        "report_date": report_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "corpus_freshness": recommendations.get("corpus_freshness", {}),
        "schedule_proof": {
            "execution_context": execution_context,
            "unattended_schedule_proven": execution_context == "launchd",
            "claim_boundary": "manual_recovery/manual_canary 可補資料，但只有真實排程 marker 才證明 unattended schedule。",
        },
        "cadence": {
            "dispatcher": "daily 08:30 Asia/Taipei",
            "day": "previous complete day", "week": "previous complete Monday-Sunday week",
            "month": "previous complete calendar month", "quarter": "previous complete calendar quarter",
            "catch_up": "missing period_id only",
        },
        "zones": {
            "EDA_IC": {
                "slug": "eda-ic", "title": "EDA／數位 IC 設計專區",
                "scope": eda_category.get("scope"), "excluded_scope": eda_category.get("excluded_scope"),
                "cycles": eda_cycles, "skills": eda_items,
                "source_review": {"reviewed": sum(_reviewed(x) for x in eda_items), "total": len(eda_items)},
                "roadmap": eda_automation_roadmap(eda_items),
                "claim_boundary": "public source review != VCS/Verdi/DC/Formality/LEC/ECO runtime proof",
            },
            "finance-investing": {
                "slug": "investing", "title": "財經投資研究專區",
                "scope": finance_category.get("scope"), "excluded_scope": finance_category.get("excluded_scope"),
                "cycles": finance_cycles, "skills": finance_items,
                "source_review": {"reviewed": sum(_reviewed(x) for x in finance_items), "total": len(finance_items)},
                "roadmap": finance_research_roadmap(finance_items),
                "claim_boundary": "research only; no trade execution, credentials, direction instruction, or profit claim",
            },
            "ai-automation": {
                "slug": "ai-automation", "title": "AI 應用／Agent Harness／Automation 情報專區",
                "scope": ai_category.get("scope"), "excluded_scope": ai_category.get("excluded_scope"),
                "cycles": ai_cycles, "skills": ai_items,
                "source_review": {"reviewed": sum(_reviewed(x) for x in ai_items), "total": len(ai_items)},
                "roadmap": ai_automation_roadmap(ai_items, ai_category.get("strategic_thesis", {})),
                "analysis_plan": ai_automation_analysis_plan(ai_category.get("strategic_thesis", {})),
                "ic_automation_blueprint": ic_design_automation_blueprint(),
                "github_breakout_lab": github_breakout_lab(ai_items, ai_history),
                "expert_methodology_desk": expert_methodology_desk(expert_watchlist),
                "intelligence_brief": ai_category.get("strategic_thesis", {}),
                "observation_tape": {
                    "started_at": ai_history.get("started_at"),
                    "days": len(ai_history.get("observations", [])),
                    "latest": ai_history.get("latest", {}),
                    "contract": ai_history.get("history_contract"),
                },
                "claim_boundary": (
                    "static public-source review and metadata only; no third-party code, private session, cookie, "
                    "anti-bot route, hosted action or confidential engineering data was used"
                ),
            },
        },
    }


def _esc(value) -> str:
    return html.escape(str(value or "—"))


def render_html(report: dict, zone_key: str, base_prefix: str = "../") -> str:
    zone = report["zones"][zone_key]
    zone_links = "".join(
        f'<a href="{_esc(base_prefix)}{_esc(item["slug"])}/">{_esc(item["title"])}</a>'
        for key, item in report["zones"].items() if key != zone_key
    )
    cycles = []
    for view in zone["cycles"]:
        if not view.get("headline"):
            body = "<p>此尺度尚無通過驗收的完整期文章。</p>"
            period = "missing"
        else:
            period = view.get("period", {}).get("period_id", "")
            actions = "".join(f"<li>{_esc(x)}</li>" for x in view.get("next_actions", []))
            falsifiers = "".join(f"<li>{_esc(x)}</li>" for x in view.get("falsifiers", []))
            body = f"""
<p class="lead">{_esc(view.get('lead'))}</p>
<p>{_esc(view.get('context'))}</p>
<h3>保留的反方觀點</h3><p>{_esc(view.get('counterpoint'))}</p>
<div class="two"><div><h3>下一步</h3><ul>{actions}</ul></div><div><h3>什麼會推翻這個判斷</h3><ul>{falsifiers}</ul></div></div>
<details><summary>證據與邊界</summary><pre>{_esc(json.dumps(view.get('evidence', {}), ensure_ascii=False, indent=2))}</pre><p>{_esc(view.get('claim_boundary'))}</p></details>"""
        cycles.append(f"""<article class="cycle" id="{_esc(view['scale'])}">
<div class="eyebrow">{_esc(view['scale_zh'])}尺度 · {_esc(period)} · {_esc(view.get('confidence'))}</div>
<h2>{_esc(view.get('headline') or view['scale_zh'] + '尺度')}</h2>{body}</article>""")

    skills = []
    for item in zone["skills"]:
        dossier = item.get("owner_dossier", {})
        role = (dossier.get("automation_role") or dossier.get("research_role")
                or dossier.get("harness_role") or "review-candidate")
        review = item.get("source_review", {})
        risks = "".join(f"<li>{_esc(x)}</li>" for x in item.get("risks", [])[:5]) or "<li>尚待逐檔補證據</li>"
        evidence = "".join(f"<li>{_esc(x)}</li>" for x in dossier.get("required_evidence", []))
        kills = "".join(f"<li>{_esc(x)}</li>" for x in dossier.get("kill_criteria", []))
        skills.append(f"""<article class="skill">
<div class="eyebrow">{_esc(item.get('recommendation_zh'))} · {_esc(review.get('status'))}{' / ' + _esc(review.get('grade')) if review.get('grade') else ''}</div>
<h3><a href="{_esc(item.get('source_url'))}">{_esc(item.get('name'))}</a></h3>
<p class="meta">{_esc(item.get('repo'))} · commit {_esc(item.get('source_commit'))} · {_esc(item.get('license'))}</p>
<p><strong>在你的系統中的角色：</strong>{_esc(role)}</p><p>{_esc(dossier.get('personalized_fit'))}</p>
<p><strong>第一個 canary：</strong>{_esc(dossier.get('first_experiment'))}</p>
<details><summary>採用證據、風險與淘汰條件</summary><h4>需要的證據</h4><ul>{evidence}</ul><h4>已知風險</h4><ul>{risks}</ul><h4>立即淘汰</h4><ul>{kills}</ul><p>{_esc(dossier.get('promotion_gate'))}</p></details>
</article>""")

    stages = []
    for stage in zone["roadmap"].get("stages", []):
        skill_names = "、".join(stage.get("skills", [])) or "尚無通過篩選的候選"
        stages.append(f"""<li><b>{_esc(stage.get('order'))}. {_esc(stage.get('title'))}</b><p>{_esc(stage.get('deliverable'))}</p><p class="meta">候選：{_esc(skill_names)}<br>證據：{_esc(stage.get('proof'))}</p></li>""")
    focus = "".join(f"<li>{_esc(x)}</li>" for x in zone["roadmap"].get("first_90_day_focus", []))
    suite = "".join(f"<code>{_esc(x)}</code> " for x in zone["roadmap"].get("internal_skill_suite", []))

    brief = zone.get("intelligence_brief", {})
    brief_html = ""
    if brief:
        catalysts = "".join(f"<li>{_esc(x)}</li>" for x in brief.get("catalysts", []))
        indicators = "".join(f"<li>{_esc(x)}</li>" for x in brief.get("leading_indicators", []))
        falsifiers = "".join(f"<li>{_esc(x)}</li>" for x in brief.get("falsifiers", []))
        tape = zone.get("observation_tape", {})
        brief_html = f"""<section class="brief"><div class="eyebrow">STRATEGIC INTELLIGENCE · {_esc(brief.get('confidence'))}</div>
<h2>{_esc(brief.get('headline'))}</h2><p class="brief-claim">{_esc(brief.get('claim'))}</p>
<div class="brief-grid"><div><h3>待爆發賽道</h3><p><b>{_esc(brief.get('potential_track'))}</b></p><p>{_esc(brief.get('owner_specialization'))}</p></div>
<div><h3>反方觀點</h3><p>{_esc(brief.get('counterpoint'))}</p></div></div>
<div class="brief-grid"><div><h3>催化劑</h3><ul>{catalysts}</ul></div><div><h3>領先指標</h3><ul>{indicators}</ul></div></div>
<details><summary>什麼會推翻這個 thesis</summary><ul>{falsifiers}</ul></details>
<p class="meta">Observation tape 自 {_esc(tape.get('started_at'))} 起，現有 {_esc(tape.get('days'))} 個真實日快照；啟用前不回填假歷史。</p></section>"""

    analysis = zone.get("analysis_plan", {})
    analysis_html = ""
    if analysis:
        horizon_cards = []
        for horizon in analysis.get("horizons", []):
            horizon_cards.append(f"""<article class="skill"><div class="eyebrow">{_esc(horizon.get('scale_zh'))}尺度研究桌</div>
<h3>{_esc(horizon.get('question'))}</h3><p><b>方法：</b>{_esc(horizon.get('method'))}</p>
<p><b>輸出：</b>{_esc(horizon.get('deliverable'))}</p><p><b>對你的工作：</b>{_esc(horizon.get('work_translation'))}</p>
<details><summary>輸入與 claim boundary</summary><p>{_esc(horizon.get('inputs'))}</p><p>{_esc(horizon.get('claim_boundary'))}</p></details></article>""")
        filters = "".join(f"<li>{_esc(x)}</li>" for x in analysis.get("niche_filters", []))
        hypotheses = "".join(
            f"<li><b>{_esc(x.get('name'))}</b><p>{_esc(x.get('why'))}</p><p class=\"meta\">Canary：{_esc(x.get('first_canary'))}<br>升級 gate：{_esc(x.get('promotion_gate'))}</p></li>"
            for x in analysis.get("priority_hypotheses", [])
        )
        workbench = analysis.get("workbench", {})
        analysis_html = f"""<section class="roadmap"><div class="eyebrow">RESEARCH DESK CONTRACT · NX_CONTEXT={_esc(workbench.get('nx_context'))}</div>
<h2>分析面板計畫：從每日訊號到季度押注</h2><p class="lead">{_esc(analysis.get('objective'))}</p><p>{_esc(analysis.get('decision_rule'))}</p>
<div class="skills">{''.join(horizon_cards)}</div><div class="two"><div><h3>利基篩選器</h3><ul>{filters}</ul></div><div><h3>對你工作最有價值的三個假設</h3><ol>{hypotheses}</ol></div></div>
<details><summary>分析工具的 authority 邊界</summary><p><b>Production：</b>{_esc(workbench.get('production'))}</p><p><b>Exploration：</b>{_esc(workbench.get('exploration'))}</p><p><b>AI：</b>{_esc(workbench.get('ai_role'))}</p></details></section>"""

    breakout = zone.get("github_breakout_lab", {})
    breakout_html = ""
    if breakout:
        breakout_rows = "".join(
            f"<tr><td><b>{_esc(item.get('name'))}</b><br><span class=\"meta\">{_esc(item.get('repo'))}</span></td>"
            f"<td>{_esc(item.get('stars'))}<br><span class=\"meta\">delta {_esc(item.get('star_delta'))}</span></td>"
            f"<td><b>{_esc(item.get('bucket'))}</b><br><span class=\"meta\">technical grade {_esc(item.get('grade'))}</span></td>"
            f"<td>{_esc(item.get('implementation_fit'))}<br><span class=\"meta\">Canary：{_esc(item.get('first_experiment'))}</span></td></tr>"
            for item in breakout.get("ranked", [])
        )
        lenses = "".join(f"<li>{_esc(item)}</li>" for item in breakout.get("lenses", []))
        breakout_html = f"""<section class="brief breakout"><div class="eyebrow">GITHUB BREAKOUT LAB · {_esc(breakout.get('status'))} · {_esc(breakout.get('history_days'))} observation day(s)</div>
<h2>出圈訊號與安靜的高品質實作</h2><p class="brief-claim">{_esc(breakout.get('thesis'))}</p>
<div class="table-wrap"><table><thead><tr><th>專案</th><th>Stars／delta</th><th>注意力 vs 技術審查</th><th>對你的可轉移價值</th></tr></thead><tbody>{breakout_rows}</tbody></table></div>
<div class="two"><div><h3>四個分析鏡頭</h3><ul>{lenses}</ul></div><div><h3>判讀邊界</h3><p>{_esc(breakout.get('velocity_boundary'))}</p><p>{_esc(breakout.get('quiet_signal_rule'))}</p></div></div></section>"""

    expert = zone.get("expert_methodology_desk", {})
    expert_html = ""
    if expert:
        deployment_brief = expert.get("deployment_brief_contract", {})
        deployment_brief_html = ""
        if deployment_brief:
            horizon_cards = "".join(
                f"<article class=\"skill\"><div class=\"eyebrow\">{_esc(item.get('cadence')).upper()} · {_esc(item.get('id')).upper()}</div>"
                f"<h3>{_esc(item.get('title'))}</h3><p>{_esc(item.get('decision'))}</p>"
                f"<p class=\"meta\">輸出：{_esc(item.get('output'))}</p></article>"
                for item in deployment_brief.get("horizons", [])
            )
            story_anatomy = "".join(
                f"<li>{_esc(item)}</li>" for item in deployment_brief.get("story_anatomy", [])
            )
            priority_gate = "".join(
                f"<li>{_esc(item)}</li>" for item in deployment_brief.get("priority_gate", [])
            )
            live_issue = deployment_brief.get("live_issue")
            live_issue_text = (
                _esc(live_issue)
                if live_issue
                else "尚無 live issue；先建立 append-only observation，再由真實新增證據產生第一期。"
            )
            deployment_brief_html = f"""<div class="deployment-brief"><div class="eyebrow">AI DEPLOYMENT FIELD BRIEF · {_esc(deployment_brief.get('status'))}</div>
<h3>{_esc(deployment_brief.get('title'))}</h3><p class="brief-claim">{_esc(deployment_brief.get('editorial_rule'))}</p>
<div class="skills">{horizon_cards}</div><div class="two"><div><h3>每篇快報的六段骨架</h3><ol>{story_anatomy}</ol></div>
<div><h3>進入頭條前的四道 gate</h3><ol>{priority_gate}</ol></div></div>
<p class="notice"><b>目前發刊狀態：</b>{live_issue_text}</p><p class="meta">{_esc(deployment_brief.get('history_contract'))}</p></div>"""
        source_cards = []
        for source_name, source in expert.get("source_status", {}).items():
            source_cards.append(
                f"<article class=\"skill\"><div class=\"eyebrow\">{_esc(source_name).upper()}</div>"
                f"<h3>{_esc(source.get('status'))}</h3><p>{_esc(source.get('boundary'))}</p>"
                f"<p class=\"meta\">observed {_esc(source.get('observed_at'))}</p></article>"
            )
        track_cards = []
        for track in expert.get("tracks", []):
            people = []
            layer_counts = {}
            for person in track.get("experts", []):
                handle = f"@{person.get('x')}" if person.get("x") else "X：未指定"
                primary = person.get("primary")
                name = _esc(person.get("name"))
                name_html = f'<a href="{_esc(primary)}">{name}</a>' if primary else name
                role = person.get("role_type")
                layer = person.get("deployment_layer")
                if layer:
                    layer_counts[layer] = layer_counts.get(layer, 0) + 1
                deployment_meta = (
                    f"<br><span class=\"signal-meta\">角色 {_esc(role)} · layer {_esc(layer)}</span>"
                    if role or layer else ""
                )
                people.append(
                    f"<li><b>{name_html}</b> · {_esc(handle)} · {_esc(person.get('authority'))}"
                    f"<br><span class=\"meta\">{_esc(person.get('why'))}</span>{deployment_meta}</li>"
                )
            layer_summary = "".join(
                f"<span>{_esc(layer)} {_esc(count)}</span>"
                for layer, count in sorted(layer_counts.items())
            )
            source_count = len(track.get("experts", []))
            track_cards.append(
                f"<article class=\"skill\"><div class=\"eyebrow\">EXPERT TRACK</div><h3>{_esc(track.get('title'))}</h3>"
                f"<p>{_esc(track.get('question'))}</p>"
                f"<p class=\"track-stats\"><span>{source_count} 位來源</span>{layer_summary}</p>"
                f"<details><summary>展開人物與一手來源</summary><ul>{''.join(people)}</ul></details></article>"
            )
        cadence = "".join(f"<li>{_esc(item)}</li>" for item in expert.get("cadence", []))
        card_contract = "".join(f"<li>{_esc(item)}</li>" for item in expert.get("daily_card_contract", []))
        reddit_rows = "".join(
            f"<tr><td><a href=\"{_esc(item.get('url'))}\">{_esc(item.get('name'))}</a></td>"
            f"<td>{_esc(item.get('status'))}</td><td>{_esc(item.get('use'))}</td></tr>"
            for item in expert.get("reddit", [])
        )
        expert_html = f"""<section class="brief expert-desk"><div class="eyebrow">EXPERT METHODOLOGY DESK · {_esc(expert.get('status'))}</div>
<h2>社群大神與前沿團隊：追方法，不追聲量</h2><p class="brief-claim">每則貼文先問「新增了哪個可檢查的方法？」再回到原始碼、paper、官方文件或可重現 canary。</p>
{deployment_brief_html}
<h3>來源健康度</h3><div class="skills">{''.join(source_cards)}</div>
<h3>{len(expert.get('tracks', []))} 條 watchlist</h3><div class="skills">{''.join(track_cards)}</div>
<div class="two"><div><h3>跨週期編輯契約</h3><ol>{cadence}</ol></div><div><h3>每日方法論卡片</h3><ol>{card_contract}</ol></div></div>
<details><summary>Reddit 公開 discovery 與 claim boundary</summary><div class="table-wrap"><table><thead><tr><th>來源</th><th>可用性</th><th>用途</th></tr></thead><tbody>{reddit_rows}</tbody></table></div><p>{_esc(expert.get('claim_boundary'))}</p></details></section>"""

    blueprint = zone.get("ic_automation_blueprint", {})
    blueprint_html = ""
    if blueprint:
        principles = "".join(f"<li>{_esc(x)}</li>" for x in blueprint.get("principles", []))
        layer_cards = []
        for layer in blueprint.get("layers", []):
            build = "".join(f"<li>{_esc(x)}</li>" for x in layer.get("build", []))
            artifacts = " ".join(f"<code>{_esc(x)}</code>" for x in layer.get("artifacts", []))
            method_sources = "、".join(layer.get("skills", []))
            layer_cards.append(f"""<article class="skill"><div class="eyebrow">{_esc(layer.get('id')).upper()} PLANE</div>
<h3>{_esc(layer.get('title'))}</h3><p class="lead">{_esc(layer.get('goal'))}</p><ul>{build}</ul>
<p><b>核心產物：</b>{artifacts}</p><p><b>Promotion proof：</b>{_esc(layer.get('proof'))}</p>
<p><b>降低認知負載：</b>{_esc(layer.get('attention'))}</p><p class="meta">方法來源：{_esc(method_sources)}</p></article>""")
        ladder_rows = "".join(
            f"<tr><td><b>{_esc(x.get('tier'))}</b><br><span class=\"meta\">{_esc(x.get('when'))}</span></td><td>{_esc(x.get('gates'))}</td><td>{_esc(x.get('stop'))}</td></tr>"
            for x in blueprint.get("iteration_ladder", [])
        )
        pattern_rows = "".join(
            f"<tr><td><b>{_esc(x.get('priority'))}</b></td><td><b>{_esc(x.get('name'))}</b><br>{_esc(x.get('pattern'))}</td><td>{_esc(x.get('catches'))}</td></tr>"
            for x in blueprint.get("verification_patterns", [])
        )
        mvp = "".join(
            f"<li><b>{_esc(x.get('phase'))}</b><p>{_esc(x.get('build'))}</p><p class=\"meta\">Exit：{_esc(x.get('exit'))}</p></li>"
            for x in blueprint.get("mvp", [])
        )
        metrics = "".join(f"<li>{_esc(x)}</li>" for x in blueprint.get("metrics", []))
        reuse_rows = "".join(
            f"<tr><td>{_esc(x.get('candidate'))}</td><td><b>{_esc(x.get('decision'))}</b></td><td>{_esc(x.get('boundary'))}</td></tr>"
            for x in blueprint.get("reuse_ledger", [])
        )
        owner = blueprint.get("owner_decision", {})
        blueprint_html = f"""<section class="brief blueprint"><div class="eyebrow">IC DESIGN AUTOMATION BLUEPRINT · {_esc(blueprint.get('status'))} · {_esc(blueprint.get('context'))}</div>
<h2>IC Design Automation：從環境到驗證的 build-up 路線</h2><p class="brief-claim">{_esc(blueprint.get('north_star'))}</p>
<div class="two"><div><h3>不可妥協原則</h3><ul>{principles}</ul></div><div><h3>建議 owner decision</h3><p>{_esc(owner.get('recommendation'))}</p><p class="meta">替代：{_esc(owner.get('alternative'))}<br>若暫緩：{_esc(owner.get('default_if_deferred'))}<br>requires_owner_approval={_esc(owner.get('requires_owner_approval'))}</p></div></div>
<h3>六層 build architecture</h3><div class="skills">{''.join(layer_cards)}</div>
<h3>分層 verification ladder</h3><div class="table-wrap"><table><thead><tr><th>Gate</th><th>要跑的證據</th><th>停止／claim boundary</th></tr></thead><tbody>{ladder_rows}</tbody></table></div>
<h3>最重要的 verification patterns</h3><div class="table-wrap"><table><thead><tr><th>優先</th><th>Pattern</th><th>主要防止</th></tr></thead><tbody>{pattern_rows}</tbody></table></div>
<div class="two"><div><h3>90 天 MVP</h3><ol>{mvp}</ol></div><div><h3>只量測可觀察成果</h3><ul>{metrics}</ul></div></div>
<details><summary>Reuse ledger 與 realm boundary</summary><div class="table-wrap"><table><thead><tr><th>候選</th><th>決策</th><th>邊界</th></tr></thead><tbody>{reuse_rows}</tbody></table></div></details></section>"""

    schedule = report["schedule_proof"]
    tabs = "".join(
        (
            f'<a href="{_esc(base_prefix)}{_esc(zone["slug"])}/{_esc(view["scale"])}/{_esc(view.get("period",{}).get("period_id","index"))}.html">{_esc(view["scale_zh"])}</a>'
            if view.get("status") == "AI_GENERATED"
            else f'<a href="#{_esc(view["scale"])}">{_esc(view["scale_zh"])} · 歷史不足</a>'
        ) for view in zone["cycles"]
    )
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(zone['title'])} · Skills Radar</title><style>
:root{{--bg:#f7f5f0;--paper:#fff;--ink:#20201d;--dim:#6e6a62;--line:#ddd7cc;--accent:#9b4b27;--ok:#2d6a4f}}@media(prefers-color-scheme:dark){{:root{{--bg:#151513;--paper:#1e1e1b;--ink:#eeeae2;--dim:#aaa49a;--line:#3a3731;--accent:#e28a5c;--ok:#7ac29b}}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;line-height:1.72}}main{{max-width:1120px;min-width:0;margin:auto;padding:1.4rem 1.1rem 5rem}}a{{color:var(--accent)}}nav{{display:flex;gap:.9rem;flex-wrap:wrap;padding:.7rem 0}}.hero{{padding:3.3rem 0 2rem;max-width:850px}}h1{{font-size:clamp(2rem,5vw,4rem);line-height:1.08;margin:.3rem 0}}h2{{line-height:1.2}}.eyebrow,.meta{{color:var(--dim);font-size:.84rem}}.notice,.cycle,.skill,.roadmap,.brief{{min-width:0;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1.15rem 1.25rem;margin:1rem 0}}.notice{{border-left:4px solid var(--accent)}}.lead,.brief-claim{{font-size:1.12rem}}.brief{{border-top:5px solid var(--ink);border-radius:0}}.blueprint{{border-top-color:var(--accent)}}.breakout{{border-top-color:#7b2cbf}}.expert-desk{{border-top-color:#147d92}}.deployment-brief{{min-width:0;border:1px solid var(--line);border-left:5px solid #147d92;padding:1rem 1.15rem;margin:1.2rem 0;background:var(--paper)}}.signal-meta{{display:inline-block;color:#147d92;font-size:.78rem;margin:.2rem 0 .7rem}}.track-stats{{display:flex;gap:.4rem;flex-wrap:wrap}}.track-stats span{{border:1px solid var(--line);border-radius:999px;padding:.2rem .55rem;color:var(--dim);font-size:.75rem}}.brief-grid{{display:grid;gap:1rem;min-width:0}}.tabs{{display:flex;gap:.5rem;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);padding:.7rem 0;z-index:2}}.tabs a{{padding:.35rem .8rem;border:1px solid var(--line);border-radius:999px;background:var(--paper)}}.two,.skills{{display:grid;gap:1rem;min-width:0}}@media(min-width:760px){{.two,.skills,.brief-grid{{grid-template-columns:1fr 1fr}}}}pre{{white-space:pre-wrap;max-width:100%;overflow:auto;font-size:.75rem}}details summary{{cursor:pointer;color:var(--accent)}}.roadmap ol{{padding-left:1.3rem}}.roadmap li{{margin:1rem 0}}.status{{color:var(--ok)}}.table-wrap{{width:100%;min-width:0;max-width:100%;overflow-x:auto;overflow-y:hidden;margin:1rem 0}}table{{width:100%;max-width:100%;table-layout:fixed;border-collapse:collapse;font-size:.92rem}}th,td{{overflow-wrap:anywhere;word-break:break-word;text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:.65rem}}th{{color:var(--dim);font-size:.8rem}}
</style></head><body><main><nav><a href="{_esc(base_prefix)}index.html">Skills Radar</a>{zone_links}<a href="{_esc(base_prefix)}editorials/">總體觀點</a><a href="{_esc(base_prefix)}recommendations/">每日清單</a></nav>
<header class="hero"><div class="eyebrow">owner-personalized research zone · {_esc(report['report_date'])}</div><h1>{_esc(zone['title'])}</h1><p class="lead">{_esc(zone['roadmap']['thesis'])}</p><p>{_esc(zone.get('scope'))}</p><p class="meta">排除：{_esc(zone.get('excluded_scope'))}</p></header>
<div class="notice"><b class="status">{_esc(report['status'])}</b> · corpus {_esc(report.get('corpus_freshness',{}).get('status'))} · source review {zone['source_review']['reviewed']}/{zone['source_review']['total']}<br>排程來源：<code>{_esc(schedule['execution_context'])}</code>；{_esc(schedule['claim_boundary'])}<br>{_esc(zone['claim_boundary'])}</div>
{brief_html}
{analysis_html}
{breakout_html}
{expert_html}
{blueprint_html}
<section class="roadmap"><h2>為你設計的下一步路線</h2><ol>{''.join(stages)}</ol>{f'<h3>前九十天</h3><ul>{focus}</ul>' if focus else ''}{f'<h3>建議內部 skill suite</h3><p>{suite}</p>' if suite else ''}</section>
<div class="tabs"><span>週期文章：</span>{tabs}</div>
<section><h2>多週期 AI 觀點</h2>{''.join(cycles)}</section>
<section><h2>逐 Skill 深入研究</h2><p class="meta">顯示目前 portfolio 中的每一個候選；來源審查未完成者會明確標為 PENDING。</p><div class="skills">{''.join(skills)}</div></section>
</main></body></html>"""


def render_markdown(report: dict, zone_key: str) -> str:
    zone = report["zones"][zone_key]
    lines = [
        f"# {zone['title']} — {report['report_date']}", "",
        f"> 狀態：`{report['status']}`；排程來源：`{report['schedule_proof']['execution_context']}`。",
        f"> {zone['claim_boundary']}", "", zone["roadmap"]["thesis"], "",
    ]
    brief = zone.get("intelligence_brief", {})
    if brief:
        lines += [
            "## Strategic Intelligence Brief", "",
            f"### {brief.get('headline','—')}", "", brief.get("claim", ""), "",
            f"**待爆發賽道：{brief.get('potential_track','—')}**", "",
            brief.get("owner_specialization", ""), "",
            f"反方觀點：{brief.get('counterpoint','—')}", "",
            "### 催化劑", "",
            *[f"- {item}" for item in brief.get("catalysts", [])], "",
            "### 領先指標", "",
            *[f"- {item}" for item in brief.get("leading_indicators", [])], "",
        ]
    analysis = zone.get("analysis_plan", {})
    if analysis:
        lines += ["## 分析面板計畫：從每日訊號到季度押注", "", analysis.get("objective", ""), ""]
        for horizon in analysis.get("horizons", []):
            lines += [
                f"### {horizon.get('scale_zh')}尺度：{horizon.get('question')}", "",
                f"- 方法：{horizon.get('method')}",
                f"- 輸出：{horizon.get('deliverable')}",
                f"- 對你的工作：{horizon.get('work_translation')}",
                f"- 邊界：{horizon.get('claim_boundary')}", "",
            ]
        lines += ["### 優先利基假設", ""]
        for hypothesis in analysis.get("priority_hypotheses", []):
            lines += [f"- **{hypothesis.get('name')}**：{hypothesis.get('why')}",
                      f"  - Canary：{hypothesis.get('first_canary')}",
                      f"  - Promotion gate：{hypothesis.get('promotion_gate')}"]
        lines += [""]
    breakout = zone.get("github_breakout_lab", {})
    if breakout:
        lines += [
            "## GitHub Breakout Lab：出圈訊號與安靜的高品質實作", "",
            f"> `{breakout.get('status')}` · {breakout.get('history_days')} observation day(s)", "",
            breakout.get("thesis", ""), "",
            "| 專案 | Stars／delta | 注意力 bucket | 技術 grade | 對你的可轉移價值 |",
            "| --- | ---: | --- | --- | --- |",
        ]
        for item in breakout.get("ranked", []):
            lines.append(
                f"| {item.get('name')} | {item.get('stars')}／{item.get('star_delta')} | "
                f"{item.get('bucket')} | {item.get('grade')} | {item.get('implementation_fit')} |"
            )
        lines += ["", f"Velocity boundary：{breakout.get('velocity_boundary')}", "",
                  f"Quiet-signal rule：{breakout.get('quiet_signal_rule')}", ""]
    expert = zone.get("expert_methodology_desk", {})
    if expert:
        lines += ["## 社群大神與前沿團隊方法論 Desk", "",
                  "每則貼文先問新增了哪個可檢查的方法，再回到原始碼、paper、官方文件或可重現 canary。", "",
                  ]
        deployment_brief = expert.get("deployment_brief_contract", {})
        if deployment_brief:
            lines += [f"### {deployment_brief.get('title', 'AI Deployment Field Brief')}", "",
                      f"> `{deployment_brief.get('status')}`", "",
                      deployment_brief.get("editorial_rule", ""), "",
                      "#### 三個發刊尺度", ""]
            for horizon in deployment_brief.get("horizons", []):
                lines += [
                    f"- **{horizon.get('cadence')} · {horizon.get('title')}**：{horizon.get('decision')}",
                    f"  - 輸出：{horizon.get('output')}",
                ]
            lines += ["", "#### 每篇快報的六段骨架", ""]
            lines += [f"- {item}" for item in deployment_brief.get("story_anatomy", [])]
            lines += ["", "#### 進入頭條前的 gate", ""]
            lines += [f"- {item}" for item in deployment_brief.get("priority_gate", [])]
            lines += ["", "目前尚無 live issue；先建立真實 observation，不以名單或 profile 重建假新聞。", "",
                      f"> {deployment_brief.get('history_contract')}", ""]
        lines += ["### 來源健康度", ""]
        for source_name, source in expert.get("source_status", {}).items():
            lines += [f"- **{source_name.upper()} · {source.get('status')}**：{source.get('boundary')}"]
        lines += ["", f"### {len(expert.get('tracks', []))} 條 watchlist", ""]
        for track in expert.get("tracks", []):
            lines += [f"#### {track.get('title')}", "", track.get("question", ""), ""]
            for person in track.get("experts", []):
                primary = f"[{person.get('name')}]({person.get('primary')})" if person.get("primary") else person.get("name")
                handle = f"@{person.get('x')}" if person.get("x") else "X：未指定"
                deployment_meta = ""
                if person.get("role_type") or person.get("deployment_layer"):
                    deployment_meta = (
                        f"；角色 `{person.get('role_type', '—')}` · layer `{person.get('deployment_layer', '—')}`"
                    )
                lines += [
                    f"- **{primary}** · {handle} · `{person.get('authority')}`：{person.get('why')}{deployment_meta}"
                ]
            lines += [""]
        lines += ["### 日／週／月／季契約", ""]
        lines += [f"- {item}" for item in expert.get("cadence", [])]
        lines += ["", "### 每日方法論卡片", ""]
        lines += [f"- {item}" for item in expert.get("daily_card_contract", [])]
        lines += ["", f"> {expert.get('claim_boundary')}", ""]
    blueprint = zone.get("ic_automation_blueprint", {})
    if blueprint:
        lines += [
            "## IC Design Automation Build-up Blueprint", "",
            f"> `{blueprint.get('status')}` · {blueprint.get('context')}", "",
            blueprint.get("north_star", ""), "",
            "### 六層 build architecture", "",
        ]
        for layer in blueprint.get("layers", []):
            lines += [f"#### {layer.get('title')}", "", layer.get("goal", ""), ""]
            lines += [f"- Build：{item}" for item in layer.get("build", [])]
            lines += [
                f"- 核心產物：{'、'.join(layer.get('artifacts', []))}",
                f"- Promotion proof：{layer.get('proof')}",
                f"- 降低認知負載：{layer.get('attention')}", "",
            ]
        lines += ["### 分層 verification ladder", ""]
        for gate in blueprint.get("iteration_ladder", []):
            lines += [f"- **{gate.get('tier')}**（{gate.get('when')}）：{gate.get('gates')}",
                      f"  - 邊界：{gate.get('stop')}"]
        lines += ["", "### 最重要的 verification patterns", ""]
        for pattern in blueprint.get("verification_patterns", []):
            lines += [f"- **{pattern.get('priority')} · {pattern.get('name')}**：{pattern.get('pattern')}",
                      f"  - 主要防止：{pattern.get('catches')}"]
        lines += ["", "### 90 天 MVP", ""]
        for phase in blueprint.get("mvp", []):
            lines += [f"- **{phase.get('phase')}**：{phase.get('build')}", f"  - Exit：{phase.get('exit')}"]
        owner = blueprint.get("owner_decision", {})
        lines += ["", "### Owner decision", "", f"- 建議：{owner.get('recommendation')}",
                  f"- 替代：{owner.get('alternative')}", f"- 若暫緩：{owner.get('default_if_deferred')}",
                  f"- `requires_owner_approval={owner.get('requires_owner_approval')}`", ""]
    lines += ["## 多週期 AI 觀點", ""]
    for view in zone["cycles"]:
        lines += [
            f"### {view['scale_zh']}尺度 — {view.get('period',{}).get('period_id','MISSING')}", "",
            f"**{view.get('headline','尚無文章')}**", "", view.get("lead", "尚無通過驗收的文章。"), "",
            view.get("context", ""), "", f"反方觀點：{view.get('counterpoint','—')}", "",
        ]
    lines += ["## Automation／研究路線", ""]
    for stage in zone["roadmap"].get("stages", []):
        lines += [f"### {stage.get('order')}. {stage.get('title')}", "", stage.get("deliverable", ""), "",
                  f"候選：{'、'.join(stage.get('skills', [])) or '尚無'}", "", f"證據：{stage.get('proof')}", ""]
    lines += ["## 逐 Skill dossier", ""]
    for item in zone["skills"]:
        dossier = item.get("owner_dossier", {})
        role = (dossier.get("automation_role") or dossier.get("research_role")
                or dossier.get("harness_role") or "review-candidate")
        lines += [
            f"### {item.get('name')} — {item.get('recommendation_zh')}", "",
            f"- 來源：[{item.get('repo')}/{item.get('path')}]({item.get('source_url')})",
            f"- Review：{item.get('source_review',{}).get('status')} / {item.get('source_review',{}).get('grade') or '—'}",
            f"- 角色：`{role}`",
            f"- 個人化理由：{dossier.get('personalized_fit','—')}",
            f"- 第一個 canary：{dossier.get('first_experiment','—')}",
            f"- Promotion gate：{dossier.get('promotion_gate','—')}", "",
        ]
    return "\n".join(lines)


def write_outputs(report: dict, root: Path = ROOT) -> None:
    output = root / "corpus" / "domain_zones.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    mapping = {"EDA_IC": "eda-ic", "finance-investing": "investing", "ai-automation": "ai-automation"}
    for key, slug in mapping.items():
        docs = root / "docs" / slug
        research = root / "research" / "zones" / slug
        docs.mkdir(parents=True, exist_ok=True)
        research.mkdir(parents=True, exist_ok=True)
        (docs / "index.html").write_text(render_html(report, key), encoding="utf-8")
        (research / f"{report['report_date']}.md").write_text(render_markdown(report, key), encoding="utf-8")
        for view in report["zones"][key]["cycles"]:
            if view.get("status") != "AI_GENERATED":
                continue
            scale = view["scale"]
            period_id = view.get("period", {}).get("period_id")
            if not period_id:
                continue
            period_docs = docs / scale
            period_research = research / scale
            period_docs.mkdir(parents=True, exist_ok=True)
            period_research.mkdir(parents=True, exist_ok=True)
            # Keep period-keyed files immutable-by-identity. A same-period content
            # change remains visible in Git and must pass the normal review gates.
            one = json.loads(json.dumps(report, ensure_ascii=False))
            one["zones"][key]["cycles"] = [view]
            (period_docs / f"{period_id}.html").write_text(render_html(one, key, "../../"), encoding="utf-8")
            (period_research / f"{period_id}.md").write_text(render_markdown(one, key), encoding="utf-8")
            links = sorted(p.stem for p in period_docs.glob("*.html") if p.name != "index.html")
            index = "<!doctype html><meta charset=\"utf-8\"><title>period archive</title><h1>" + html.escape(SCALE_ZH[scale]) + "尺度文章</h1><ul>" + "".join(
                f'<li><a href="{html.escape(name)}.html">{html.escape(name)}</a></li>' for name in links
            ) + "</ul>"
            (period_docs / "index.html").write_text(index, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args(argv)
    report = build_report(
        load(RECOMMENDATIONS), load(TIMESCALES), load(HEALTH, {}), args.date,
        load(AI_AUTOMATION_HISTORY, {}), load(EXPERT_WATCHLIST, {}),
    )
    write_outputs(report)
    print(
        f"domain zones: {args.date}; status={report['status']}; "
        f"EDA={len(report['zones']['EDA_IC']['skills'])}; "
        f"finance={len(report['zones']['finance-investing']['skills'])}; "
        f"ai-automation={len(report['zones']['ai-automation']['skills'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
