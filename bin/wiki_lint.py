#!/usr/bin/env python3
"""
wiki_lint.py — 跨時間的矛盾偵測。零 token。

出處：Karpathy 的 LLM Wiki 概念（三層：raw sources / wiki / schema，三操作：ingest / query / lint）。
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

他點出的問題正好是本專案的缺陷：每日報告是「重新生成」而非「累積修正」，
所以昨天講錯的話今天不會被發現，只會多一個檔案。

這支程式做 lint：把歷來報告中的**量化宣稱**抽出來，同一個指標跨日期比對，
若前後說法互相矛盾就標出來，強迫「要嘛修正、要嘛說明為什麼變了」。

實例：本專案曾對「硬體領域的 verify 佔比」先後宣稱 8.3% → 2.24x → 16.0%，
前兩者都是樣本不足或模型過度自信造成的錯誤。有這支程式就會在第二次當下被擋下。
"""
import json, os, re, sys, glob
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 要追蹤的指標：名稱 → 在文字中辨識它的樣態（需含一個數字捕捉群）
# 每個指標：(擷取樣態, 必須同時出現在鄰近文字的限定詞)
# 限定詞是關鍵——沒有它，各領域的 verify 百分比會被誤當成「全體」指標。
GLOBAL = r"(全體|整體|總體|全域|平均|global|overall)"
METRICS = {
    "全體 verify 佔比": ([r"verify[^\n。]{0,20}?(\d{1,3}(?:\.\d)?)\s*%",
                       r"驗證[^\n。]{0,14}?(\d{1,3}(?:\.\d)?)\s*%"], GLOBAL),
    "全體上線率": ([r"production[^\n。]{0,16}?(\d{1,3}(?:\.\d)?)\s*%",
                r"上線率[^\n。]{0,14}?(\d{1,3}(?:\.\d)?)\s*%"], GLOBAL),
    "硬體EDA佔母體比例": ([r"硬體\s*/?\s*EDA[^\n。]{0,24}?(\d{1,2}(?:\.\d{1,2})?)\s*%"],
                    r"(佔|中立樣本|母體)"),
    "語料規模": ([r"(\d{1,3}(?:,\d{3})+)\s*(?:筆|個)\s*(?:公開\s*)?(?:SKILL|skill|樣本)"], None),
    "注入掃描命中率": ([r"命中[^\n。]{0,16}?(\d{1,2}(?:\.\d{1,2})?)\s*%"], r"(掃描|注入|injection)"),
}
EXTERNAL_CORPUS_MARKERS = re.compile(
    r"Snyk|ToxicSkills|GitHub\s*上有|外部(?:研究|資料集)|論文(?:掃描|樣本)", re.I
)

def collect(path):
    """從一份報告抽出所有可追蹤的量化宣稱。

    以「句子」為單位判定限定詞歸屬——這是唯一同時避開兩種錯誤的做法：
      · 固定字元窗口太短 → 漏掉「全體任務分佈基準為：verify (15.0%)…」（限定詞在句首）
      · 前後雙向窗口     → 誤配「healthcare-bio（53.4%）…遠高於總體平均（42.3%）」
    規則：限定詞必須與數字同句，且出現在數字之前。
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        t = fh.read()
    if "<!-- WIKI-LINT:SUPERSEDED -->" in t:
        return defaultdict(list)
    found = defaultdict(list)
    # 依句末標點與換行切句；保留原文以便回報上下文
    sentences = re.split(r"(?<=[。！？\n])", t)
    for sent in sentences:
        if not sent.strip():
            continue
        for name, (pats, require) in METRICS.items():
            # Named external studies and the GitHub-wide universe are not this
            # project's corpus size.  Comparing them creates a false conflict.
            if name == "語料規模" and EXTERNAL_CORPUS_MARKERS.search(sent):
                continue
            for p in pats:
                for m in re.finditer(p, sent):
                    try:
                        v = float(m.group(1).replace(",", ""))
                    except ValueError:
                        continue
                    if require:
                        before = sent[:m.start()]
                        if not re.search(require, before, re.I):
                            continue
                    found[name].append({
                        "value": v,
                        "ctx": re.sub(r"\s+", " ", sent.strip())[:200],
                    })
    return found


def validate_entity_wiki():
    """Validate the cumulative wiki ledger and all current entity pages."""
    errors = []
    history_path = os.path.join(ROOT, "data", "wiki_history.json")
    if not os.path.exists(history_path):
        return ["data/wiki_history.json missing"]
    try:
        history = json.load(open(history_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"wiki history unreadable: {exc}"]
    snapshots = history.get("snapshots")
    if history.get("schema_version") != 1 or not isinstance(snapshots, list) or not snapshots:
        return ["wiki history schema/version invalid or empty"]
    latest = snapshots[-1]
    domains = latest.get("domains", {})
    overall_n = latest.get("overall", {}).get("n_total")
    domain_n = sum(item.get("n", 0) for item in domains.values())
    if overall_n != domain_n:
        errors.append(f"latest n_total {overall_n} != domain sum {domain_n}")
    targeted_policy = latest.get("policy", {}).get("targeted", "")
    if "all targeted-* excluded" not in targeted_policy:
        errors.append("latest policy does not exclude all targeted-*")
    if latest.get("policy", {}).get("raw_third_party_text") != "excluded":
        errors.append("latest policy does not exclude raw third-party text")
    for domain in domains:
        md = os.path.join(ROOT, "research", "wiki", f"{domain}.md")
        page = os.path.join(ROOT, "docs", "wiki", f"{domain}.html")
        if not os.path.exists(md):
            errors.append(f"missing research wiki page: {domain}")
        elif "<!-- OWNER-NOTES:START -->" not in open(md, encoding="utf-8").read():
            errors.append(f"owner notes marker missing: {domain}")
        if not os.path.exists(page):
            errors.append(f"missing docs wiki page: {domain}")
    return errors

def main():
    files = sorted(glob.glob(os.path.join(ROOT, "research", "insights", "*.md"))) \
          + sorted(glob.glob(os.path.join(ROOT, "research", "*.md"))) \
          + sorted(glob.glob(os.path.join(ROOT, "daily", "*.md")))
    if not files:
        print("[lint] 無報告可檢查"); return 0

    hist = defaultdict(list)   # metric → [(file, value, ctx)]
    for f in files:
        for name, vals in collect(f).items():
            for v in vals:
                hist[name].append((os.path.relpath(f, ROOT), v["value"], v["ctx"]))

    conflicts = []
    for name, entries in hist.items():
        vals = [e[1] for e in entries]
        if len(set(vals)) <= 1:
            continue
        lo, hi = min(vals), max(vals)
        # 相對差異超過 25% 視為互相矛盾（同一指標不該差這麼多）
        if lo > 0 and (hi - lo) / lo > 0.25:
            by_file = defaultdict(list)
            for f, v, c in entries:
                by_file[f].append(v)
            conflicts.append({
                "metric": name, "min": lo, "max": hi,
                "spread_pct": round(100 * (hi - lo) / lo, 1),
                "by_file": {f: sorted(set(v)) for f, v in by_file.items()},
                "samples": [{"file": f, "value": v, "ctx": c[:150]} for f, v, c in entries[:6]],
            })

    wiki_errors = validate_entity_wiki()
    out = {"n_files": len(files), "n_metrics_tracked": len(hist),
           "n_conflicts": len(conflicts), "conflicts": conflicts,
           "n_wiki_errors": len(wiki_errors), "wiki_errors": wiki_errors}
    json.dump(out, open(os.path.join(ROOT, "corpus", "wiki_lint.json"), "w"),
              ensure_ascii=False, indent=1)

    print(f"[lint] 檢查 {len(files)} 份報告、{len(hist)} 個指標")
    if not conflicts and not wiki_errors:
        print("[lint] 未發現跨報告矛盾，Wiki ledger 與實體頁面一致")
        return 0
    if conflicts:
        print(f"[lint] ⚠️ 發現 {len(conflicts)} 個指標前後說法不一致：\n")
        for c in conflicts:
            print(f"  ▸ {c['metric']}：{c['min']} ~ {c['max']}（相對差 {c['spread_pct']}%）")
            for f, vs in c["by_file"].items():
                print(f"      {f}: {vs}")
            print()
        print("處置：要嘛修正舊報告，要嘛在新報告中明確說明「為什麼數字變了」。")
    if wiki_errors:
        print(f"[lint] ⚠️ Wiki 結構錯誤 {len(wiki_errors)} 件：")
        for error in wiki_errors:
            print(f"      {error}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
