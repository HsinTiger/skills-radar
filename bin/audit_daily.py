#!/usr/bin/env python3
"""
稽核每日簡報：把簡報裡「可查證的具體事實」抽出來，比對當天的事實檔。
抓的是最會出幻覺的四類：版本號、arXiv 編號、repo 全名、大數字。
用法: audit_daily.py [YYYY-MM-DD]
回傳非 0 表示有可疑宣稱，需人工確認。
"""
import json, os, re, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
note_p = os.path.join(ROOT, "daily", f"{date}.md")
facts_p = os.path.join(ROOT, "data", f"facts-{date}.json")

if not (os.path.exists(note_p) and os.path.exists(facts_p)):
    print(f"[audit] 缺檔案，略過 ({date})")
    sys.exit(0)

note = open(note_p, encoding="utf-8").read()
blob = json.dumps(json.load(open(facts_p)), ensure_ascii=False)

# 已知基準事實：來自 Snyk ToxicSkills 研究，不在每日事實檔裡，屬允許引用的常數
BASELINE = {"3,984", "3984", "36.82", "13.4", "76", "1,467", "1467", "8", "30", "91", "100"}

patterns = {
    "版本號": r"v\d+\.\d+\.\d+",
    "arXiv": r"\b\d{4}\.\d{4,5}\b",
    "repo": r"\b[A-Za-z0-9][\w.-]+/[\w.-]+\b",
    "大數字": r"\b\d{1,3}(?:,\d{3})+\b",
}
suspect = []
for kind, pat in patterns.items():
    for m in set(re.findall(pat, note)):
        if m in BASELINE:
            continue
        if kind == "repo" and not re.search(r"[A-Za-z]", m.split("/")[-1]):
            continue
        # repo 可能只在描述中以短名出現，放寬為兩段皆須出現
        if m in blob or m.replace(",", "") in blob:
            continue
        if kind == "repo":
            owner, name = m.split("/", 1)
            if owner in blob and name in blob:
                continue
        suspect.append((kind, m))

if suspect:
    print(f"[audit] {date} 有 {len(suspect)} 個宣稱在事實檔中查無，需人工確認：")
    for k, v in sorted(suspect):
        print(f"   - {k}: {v}")
    sys.exit(1)
print(f"[audit] {date} 通過：所有具體宣稱均可回溯事實檔")
