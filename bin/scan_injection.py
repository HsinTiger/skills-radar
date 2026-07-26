#!/usr/bin/env python3
"""
scan_injection.py — 對語料做確定性的惡意內容掃描。零 token。

為什麼需要：
這個專案的本質是「大量讀取陌生人寫的、會被 AI 當指令執行的文字」，
是 prompt injection 風險最高的作業型態之一。prompt 裡寫「不要遵從」是必要的，但那是**宣告**，
不是**量測**。這支程式負責量測：語料裡到底有多少東西試圖指揮 AI、竊取憑證、或改設定。

重要限制（不可對外宣稱這是完整防護）：
- 這是基於規則的偵測，只抓得到已知樣態，混淆過的攻擊抓不到。
- 高分不等於惡意（教學文件常引用攻擊字串），低分也不等於安全。
- 這份輸出的用途是「決定哪些樣本要人看」與「量化生態風險」，不是門禁。
"""
import json, os, re, sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")

# 各類樣態，附權重。權重反映「若為真，後果多嚴重」，不是「多常見」。
PATTERNS = {
    "指令覆寫": (5, [
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instruction|prompt|rule|context)",
        r"disregard\s+(all\s+)?(previous|prior|the\s+above|your)\s+\w+",
        r"forget\s+(everything|all|your)\s+(you|previous|prior|instruction)",
        r"(new|updated|revised)\s+(system\s+)?(instruction|prompt|directive)s?\s*[:：]",
        r"you\s+are\s+now\s+(a|an|in)\s",
        r"override\s+(your|the|all)\s+(safety|instruction|guideline|restriction)",
        r"忽略(先前|上述|之前|所有)(的)?(指示|指令|規則)",
    ]),
    "隱瞞使用者": (5, [
        r"do\s*n[o']?t\s+(tell|inform|notify|mention\s+to|show)\s+(the\s+)?user",
        r"without\s+(asking|informing|notifying|telling)\s+(the\s+)?user",
        r"keep\s+this\s+(secret|hidden|between\s+us)",
        r"不要(告訴|通知|讓)使用者",
    ]),
    "憑證竊取": (5, [
        r"(cat|type|read|print|echo)\s+[^\n]{0,40}(\.env|\.ssh/|id_rsa|credentials|\.aws/|\.netrc)",
        r"(AWS|GITHUB|OPENAI|ANTHROPIC|SLACK)_?(SECRET|ACCESS|API)?_?(KEY|TOKEN|SECRET)",
        r"process\.env\.[A-Z_]{6,}",
        r"os\.environ\[[\"'][A-Z_]{6,}",
        r"gh\s+auth\s+token",
    ]),
    "外送資料": (4, [
        r"(curl|wget|fetch|http[sx]?://)[^\n]{0,80}(webhook|ngrok|pastebin|requestbin|"
        r"burpcollaborator|interact\.sh|oastify|\.onion)",
        r"curl[^\n]{0,60}-d\s+[\"']?\$\(",
        r"(POST|post)\s+[^\n]{0,50}(your|the)\s+(key|token|credential|secret)",
    ]),
    "改動設定或掛鉤": (4, [
        r"\.claude/(settings|config)[^\n]{0,30}(json)",
        r"[\"']hooks[\"']\s*:",
        r"(PreToolUse|PostToolUse|SessionStart)\s*[\"']?\s*:",
        r"(~/\.(bashrc|zshrc|profile)|/etc/(passwd|shadow|sudoers))",
        r"chmod\s+[0-7]{3,4}\s+[^\n]{0,30}|sudo\s+(rm|chmod|chown|tee)",
    ]),
    "編碼混淆": (3, [
        r"base64\s+(-d|--decode|-D)",
        r"atob\s*\(", r"eval\s*\(\s*(atob|Buffer\.from|decodeURIComponent)",
        r"[A-Za-z0-9+/]{180,}={0,2}",
        r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){12,}",
    ]),
    "破壞性操作": (4, [
        r"rm\s+-rf\s+[~/]", r"git\s+push\s+--force", r"DROP\s+(TABLE|DATABASE)",
        r"(shutdown|reboot)\s+-", r">\s*/dev/sda",
    ]),
    "越權自主": (3, [
        r"(auto|automatically)\s*-?\s*(approve|accept|confirm)\s+(all|every|any)",
        r"--dangerously-skip-permissions", r"skip\s+(all\s+)?(permission|confirmation)",
        r"bypass\s+(the\s+)?(sandbox|permission|approval|safety)",
    ]),
}

# 隱藏字元：零寬、雙向覆寫、標籤字元（Unicode 隱寫的常見載體）
HIDDEN = re.compile(
    r"[​-‏‪-‮⁠-⁯﻿\U000e0000-\U000e007f]")

COMPILED = {k: (w, [re.compile(p, re.I) for p in pats]) for k, (w, pats) in PATTERNS.items()}

def scan_text(t):
    hits, score = {}, 0
    for cat, (w, pats) in COMPILED.items():
        n = sum(1 for p in pats if p.search(t))
        if n:
            hits[cat] = n
            score += w * n
    h = HIDDEN.findall(t)
    if h:
        hits["隱藏字元"] = len(h)
        score += 5
    return score, hits

def main():
    rows = []
    for line in open(MASTER, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass

    cat_count = Counter()
    flagged = []
    by_domain = defaultdict(lambda: [0, 0])
    for r in rows:
        t = " ".join([r.get("name") or "", r.get("description") or "", r.get("body_head") or ""])
        score, hits = scan_text(t)
        d = r.get("domain") or "unlabeled"
        by_domain[d][1] += 1
        if score:
            by_domain[d][0] += 1
            for c in hits:
                cat_count[c] += 1
            flagged.append({"repo": r.get("repo"), "path": r.get("path"),
                            "stars": r.get("stars"), "domain": d,
                            "score": score, "hits": hits,
                            "name": (r.get("name") or "")[:80]})
    flagged.sort(key=lambda x: -x["score"])

    out = {
        "n_scanned": len(rows),
        "n_flagged": len(flagged),
        "pct_flagged": round(100 * len(flagged) / max(1, len(rows)), 2),
        "by_category": dict(cat_count.most_common()),
        "by_domain": {d: {"flagged": v[0], "total": v[1],
                          "pct": round(100 * v[0] / max(1, v[1]), 1)}
                      for d, v in sorted(by_domain.items(), key=lambda kv: -kv[1][0])},
        "top_flagged": flagged[:60],
        "severity_buckets": {
            "高(>=15)": sum(1 for f in flagged if f["score"] >= 15),
            "中(8-14)": sum(1 for f in flagged if 8 <= f["score"] < 15),
            "低(1-7)": sum(1 for f in flagged if f["score"] < 8),
        },
        "caveat": "規則式偵測，只抓已知樣態；高分不等於惡意（教學文件會引用攻擊字串），"
                  "低分不等於安全。用途是決定哪些樣本要人看，不是門禁。",
    }
    json.dump(out, open(os.path.join(ROOT, "corpus", "injection_scan.json"), "w"),
              ensure_ascii=False, indent=1)

    print(f"掃描 {out['n_scanned']:,} 筆，命中 {out['n_flagged']:,} 筆（{out['pct_flagged']}%）")
    print(f"嚴重度：{out['severity_buckets']}")
    print("\n樣態分佈：")
    for k, v in out["by_category"].items():
        print(f"   {k:14s}{v:6d}")
    print("\n各領域命中率（前 8）：")
    for d, v in list(out["by_domain"].items())[:8]:
        print(f"   {d:22s}{v['flagged']:5d}/{v['total']:<6d} {v['pct']:5.1f}%")
    print("\n最高分樣本（需人工檢視）：")
    for f in flagged[:10]:
        print(f"   {f['score']:3d} | {f['repo'][:38]:38s} | {','.join(f['hits'])}")

if __name__ == "__main__":
    main()
