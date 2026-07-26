#!/usr/bin/env python3
"""稽核洞察專區：報告裡的數字必須回溯得到訊號表。零 token。"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
date = sys.argv[1] if len(sys.argv) > 1 else ""
note_p = os.path.join(ROOT, "research", "insights", f"{date}.md")
sig_p = os.path.join(ROOT, "corpus", "opportunity.json")
if not os.path.exists(note_p):
    print(f"[validate] 無 {date} 洞察檔，略過"); sys.exit(0)
note = open(note_p, encoding="utf-8", errors="replace").read()
blob = json.dumps(json.load(open(sig_p)), ensure_ascii=False)
blob_nc = blob.replace(",", "")
suspect = []
for m in set(re.findall(r"\b\d+\.\d\b|\b\d{2,}\b", note)):
    if m in blob or m.replace(",", "") in blob_nc: continue
    # 百分比可能被四捨五入呈現，容許 ±0.1
    try:
        v = float(m)
        if any(abs(v - float(x)) <= 0.15 for x in re.findall(r"\d+\.\d", blob)): continue
    except ValueError: pass
    suspect.append(m)
if suspect:
    print(f"[validate] {date} 有 {len(suspect)} 個數字查無來源：{sorted(suspect)[:15]}")
    sys.exit(1)
print(f"[validate] {date} 通過")
