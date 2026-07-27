#!/usr/bin/env python3
"""Build the daily owner-facing EDA/IC and finance skill recommendations.

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


def github_url(repo: str, path: str, commit: str | None) -> str:
    ref = commit if commit and commit != "UNKNOWN" else "HEAD"
    return f"https://github.com/{repo}/blob/{ref}/{quote(path, safe='/._-')}"


def _matches(text: str, patterns) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _eda_use(fit: list[str]) -> str:
    joined = " ".join(fit).lower()
    if any(x in joined for x in ("fsdb", "simulation", "vcs", "verdi", "coverage")):
        return "在正式 compile/sim 之後引用其 waveform、coverage 與 debug evidence contract。"
    if any(x in joined for x in ("cycle contract", "rtl design", "handoff")):
        return "在寫 RTL 前先固化 cycle contract；交接時分開結構、功能與 signoff 證據。"
    if any(x in joined for x in ("testbench", "scoreboard", "ready-valid")):
        return "用於 testbench checklist、bounded wait、scoreboard 與 payload integrity；重寫成既有 framework。"
    if any(x in joined for x in ("sva", "formal", "assertion")):
        return "只生成綁定 spec requirement 的 candidate property，再交由正式 formal flow 證明。"
    if any(x in joined for x in ("synthesis", "lint", "lec", "sdc")):
        return "引用 evidence manifest 與 claim boundary；命令、SDC、library、corner 以 golden flow 為準。"
    return "只抽取可審查的 procedure/checklist，先在非機密 toy design 驗證。"


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
        elif grade == "C" and any(word in decision_text for word in ("不要安裝", "不納入", "不直接引用")):
            recommendation = "exclude"
        else:
            recommendation = "watch"
        commit = review.get("commit") or "UNKNOWN"
        owner_fit = candidate.get("owner_fit") or ("direct" if grade == "A" else "supporting")
        item = {
            "name": candidate.get("name") or Path(review.get("path", "SKILL.md")).parent.name or "skill",
            "repo": review.get("repo"),
            "path": review.get("path"),
            "source_commit": commit,
            "source_url": github_url(review.get("repo", ""), review.get("path", ""), commit),
            "license": review.get("license", "UNKNOWN"),
            "category": "EDA_IC",
            "owner_fit": owner_fit,
            "recommendation": recommendation,
            "recommendation_zh": STATUS_ZH[recommendation],
            "score": grade_score.get(grade, 0) + (3 if review.get("commit_verified") else 0),
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
                "source review 不等於 VCS/Verdi/DC/PrimeTime runtime PASS",
                "parser、lint 或 open-source tool PASS 不等於產品 RTL 正確或 signoff",
            ],
        }
        items.append(item)
    items.sort(key=lambda x: (-x["score"], x["repo"], x["path"]))
    recommendations = [x for x in items if x["recommendation"] != "exclude"][:8]
    excluded = [x for x in items if x["recommendation"] == "exclude"][:6]
    counts = Counter(x["recommendation"] for x in items)
    return {
        "label": "EDA / 數位 IC（WiFi baseband ASIC）",
        "scope": "規格、fixed-point、microarchitecture、RTL、lint/CDC/RDC、formal/SVA、VCS/Verdi、UVM、synthesis/STA/power 與 RTL integration。",
        "excluded_scope": "FPGA/Vivado/Quartus/bitstream、MCU/firmware/embedded、board/PCB、analog/RF/antenna。",
        "summary": (
            f"已審 {len(items)} 個來源；{counts.get('pilot', 0)} 個可沙盒試行、"
            f"{counts.get('watch', 0)} 個待補證據、{counts.get('exclude', 0)} 個排除。"
        ),
        "recommendations": recommendations,
        "excluded": excluded,
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
    return {
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


def build_finance(rows: list[dict], freshness: dict) -> dict:
    candidates = []
    seen = set()
    for row in rows:
        item = classify_finance_candidate(row, freshness)
        if not item:
            continue
        key = (item["repo"], item["path"])
        if key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    candidates.sort(key=lambda x: (-x["score"], x["repo"] or "", x["path"] or ""))

    selected, repo_seen, capability_counts = [], set(), Counter()
    for item in candidates:
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
    excluded = [x for x in candidates if x["recommendation"] == "exclude"][:6]
    for item in selected + excluded:
        item.pop("_primary", None)
    counts = Counter(x["recommendation"] for x in selected)
    return {
        "label": "財經投資研究",
        "scope": "市場／總經資料、財報與盈餘品質、估值、產業鏈論點、風險與回測方法。",
        "excluded_scope": "自動下單、實盤交易、券商／錢包／私鑰／credential 操作，以及無證據的獲利承諾。",
        "summary": (
            f"今日選出 {len(selected)} 個研究候選：{counts.get('pilot', 0)} 個沙盒試行、"
            f"{counts.get('watch', 0)} 個觀察；全部仍待逐檔 source review。"
        ),
        "recommendations": selected,
        "excluded": excluded,
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
    for key in ("EDA_IC", "finance-investing"):
        category = report["categories"][key]
        lines += [
            f"## {category['label']}", "", category["summary"], "",
            f"範圍：{category['scope']}", "",
            f"排除：{category['excluded_scope']}", "",
            "| 建議 | Skill | 用途摘要 | 引用方式 | Source review / commit | 主要風險 |",
            "|---|---|---|---|---|---|",
        ]
        for item in category["recommendations"]:
            use = item.get("use_in_next_rtl_design") or item.get("use_in_investment_research")
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
    for key in ("EDA_IC", "finance-investing"):
        category = report["categories"][key]
        cards = []
        for item in category["recommendations"]:
            use = item.get("use_in_next_rtl_design") or item.get("use_in_investment_research")
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
                 master_path: Path, report_date: str) -> dict:
    freshness = snapshot_freshness(rows, model_report, master_path)
    categories = {
        "EDA_IC": build_eda(reviews, catalog, freshness),
        "finance-investing": build_finance(rows, freshness),
    }
    return {
        "schema_version": 1,
        "report_date": report_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_OWNER_REVIEW" if freshness["status"] == "CURRENT" else "PREVIEW_STALE_CORPUS",
        "corpus_freshness": freshness,
        "policy": {
            "states": STATUS_ZH,
            "adopt_requires": "owner approval plus domain runtime proof",
            "finance_boundary": "research only; no trade execution, brokerage/wallet access or credentials",
            "population_trend_claims": "forbidden in this recommendation artifact",
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
        read_json(ASIC_REVIEWS, {}), args.master, args.date,
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
        f"finance={len(report['categories']['finance-investing']['recommendations'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
