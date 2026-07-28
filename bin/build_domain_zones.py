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
                "month": ["檢查 spec→SVA/TB→VCS/Verdi→DC/PT 各 gate 是否仍有無人負責的斷點。"],
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
            "order": 5, "id": "signoff", "title": "Synthesis／STA claim governor",
            "skills": _skills_for_role(items, role_field, "synthesis-evidence-governor"),
            "deliverable": "RTL/filelist/tool/library/corner manifest；lint、DC、LEC、PrimeTime、power claims 分層。",
            "owner_gate": "SDC、library、corner、threshold 與 waiver 只取自 internal golden flow。",
            "proof": "真實 DC／LEC／PrimeTime／power report readback；各 gate 不互相替代。",
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
            "六十一到九十天：接 DC、Formality/LEC、PrimeTime named-corner evidence；自動改 RTL 保留在最後。",
        ],
        "internal_skill_suite": [
            "wifi-bbdd-intent-compiler", "fixed-point-bittrue-contract", "rtl-artifact-generator",
            "spec-bound-sva-generator", "vcs-evidence-runner", "verdi-fsdb-analysis",
            "dc-pt-evidence", "claim-boundary-auditor",
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


def build_report(recommendations: dict, history: dict, health: dict, report_date: str) -> dict:
    categories = recommendations.get("categories", {})
    eda_category = categories.get("EDA_IC", {})
    finance_category = categories.get("finance-investing", {})
    eda_items = _dedupe(eda_category.get("all_reviewed") or (
        eda_category.get("recommendations", []) + eda_category.get("excluded", [])
    ))
    finance_items = _dedupe(
        finance_category.get("recommendations", []) + finance_category.get("excluded", [])
    )
    eda_cycles = cycle_views(history, "EDA_IC")
    finance_cycles = cycle_views(history, "finance-investing")
    complete = all(x.get("status") == "AI_GENERATED" for x in eda_cycles + finance_cycles)
    current = (
        recommendations.get("status") == "READY_FOR_OWNER_REVIEW"
        and recommendations.get("corpus_freshness", {}).get("status") == "CURRENT"
    )
    review_complete = bool(eda_items and finance_items) and all(
        _reviewed(item) and item.get("source_commit") not in {None, "", "UNKNOWN"}
        for item in eda_items + finance_items
    )
    status = "READY_FOR_OWNER_REVIEW" if current and complete and review_complete else "PARTIAL"
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
                "claim_boundary": "public source review != VCS/Verdi/DC/PrimeTime/formal runtime proof",
            },
            "finance-investing": {
                "slug": "investing", "title": "財經投資研究專區",
                "scope": finance_category.get("scope"), "excluded_scope": finance_category.get("excluded_scope"),
                "cycles": finance_cycles, "skills": finance_items,
                "source_review": {"reviewed": sum(_reviewed(x) for x in finance_items), "total": len(finance_items)},
                "roadmap": finance_research_roadmap(finance_items),
                "claim_boundary": "research only; no trade execution, credentials, direction instruction, or profit claim",
            },
        },
    }


def _esc(value) -> str:
    return html.escape(str(value or "—"))


def render_html(report: dict, zone_key: str, base_prefix: str = "../") -> str:
    zone = report["zones"][zone_key]
    other = "finance-investing" if zone_key == "EDA_IC" else "EDA_IC"
    other_zone = report["zones"][other]
    cycles = []
    for view in zone["cycles"]:
        if view.get("status") != "AI_GENERATED":
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
        role = dossier.get("automation_role") or dossier.get("research_role") or "review-candidate"
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

    schedule = report["schedule_proof"]
    tabs = "".join(
        f'<a href="{_esc(base_prefix)}{_esc(zone["slug"])}/{_esc(view["scale"])}/{_esc(view.get("period",{}).get("period_id","index"))}.html">{_esc(view["scale_zh"])}</a>'
        for view in zone["cycles"]
    )
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(zone['title'])} · Skills Radar</title><style>
:root{{--bg:#f7f5f0;--paper:#fff;--ink:#20201d;--dim:#6e6a62;--line:#ddd7cc;--accent:#9b4b27;--ok:#2d6a4f}}@media(prefers-color-scheme:dark){{:root{{--bg:#151513;--paper:#1e1e1b;--ink:#eeeae2;--dim:#aaa49a;--line:#3a3731;--accent:#e28a5c;--ok:#7ac29b}}}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;line-height:1.72}}main{{max-width:1120px;margin:auto;padding:1.4rem 1.1rem 5rem}}a{{color:var(--accent)}}nav{{display:flex;gap:.9rem;flex-wrap:wrap;padding:.7rem 0}}.hero{{padding:3.3rem 0 2rem;max-width:850px}}h1{{font-size:clamp(2rem,5vw,4rem);line-height:1.08;margin:.3rem 0}}h2{{line-height:1.2}}.eyebrow,.meta{{color:var(--dim);font-size:.84rem}}.notice,.cycle,.skill,.roadmap{{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:1.15rem 1.25rem;margin:1rem 0}}.notice{{border-left:4px solid var(--accent)}}.lead{{font-size:1.12rem}}.tabs{{display:flex;gap:.5rem;flex-wrap:wrap;position:sticky;top:0;background:var(--bg);padding:.7rem 0;z-index:2}}.tabs a{{padding:.35rem .8rem;border:1px solid var(--line);border-radius:999px;background:var(--paper)}}.two,.skills{{display:grid;gap:1rem}}@media(min-width:760px){{.two,.skills{{grid-template-columns:1fr 1fr}}}}pre{{white-space:pre-wrap;overflow:auto;font-size:.75rem}}details summary{{cursor:pointer;color:var(--accent)}}.roadmap ol{{padding-left:1.3rem}}.roadmap li{{margin:1rem 0}}.status{{color:var(--ok)}}
</style></head><body><main><nav><a href="{_esc(base_prefix)}index.html">Skills Radar</a><a href="{_esc(base_prefix)}{_esc(other_zone['slug'])}/">{_esc(other_zone['title'])}</a><a href="{_esc(base_prefix)}editorials/">總體觀點</a><a href="{_esc(base_prefix)}recommendations/">每日清單</a></nav>
<header class="hero"><div class="eyebrow">owner-personalized research zone · {_esc(report['report_date'])}</div><h1>{_esc(zone['title'])}</h1><p class="lead">{_esc(zone['roadmap']['thesis'])}</p><p>{_esc(zone.get('scope'))}</p><p class="meta">排除：{_esc(zone.get('excluded_scope'))}</p></header>
<div class="notice"><b class="status">{_esc(report['status'])}</b> · corpus {_esc(report.get('corpus_freshness',{}).get('status'))} · source review {zone['source_review']['reviewed']}/{zone['source_review']['total']}<br>排程來源：<code>{_esc(schedule['execution_context'])}</code>；{_esc(schedule['claim_boundary'])}<br>{_esc(zone['claim_boundary'])}</div>
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
        "## 多週期 AI 觀點", "",
    ]
    for view in zone["cycles"]:
        lines += [
            f"### {view['scale_zh']}尺度 — {view.get('period',{}).get('period_id','MISSING')}", "",
            f"**{view.get('headline','尚無文章')}**", "", view.get("lead", "尚無通過驗收的文章。"), "",
            view.get("context", ""), "", f"反方觀點：{view.get('counterpoint','—')}", "",
        ]
    lines += ["## ASIC automation／研究路線", ""]
    for stage in zone["roadmap"].get("stages", []):
        lines += [f"### {stage.get('order')}. {stage.get('title')}", "", stage.get("deliverable", ""), "",
                  f"候選：{'、'.join(stage.get('skills', [])) or '尚無'}", "", f"證據：{stage.get('proof')}", ""]
    lines += ["## 逐 Skill dossier", ""]
    for item in zone["skills"]:
        dossier = item.get("owner_dossier", {})
        role = dossier.get("automation_role") or dossier.get("research_role") or "review-candidate"
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
    mapping = {"EDA_IC": "eda-ic", "finance-investing": "investing"}
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
    report = build_report(load(RECOMMENDATIONS), load(TIMESCALES), load(HEALTH, {}), args.date)
    write_outputs(report)
    print(
        f"domain zones: {args.date}; status={report['status']}; "
        f"EDA={len(report['zones']['EDA_IC']['skills'])}; "
        f"finance={len(report['zones']['finance-investing']['skills'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
