#!/usr/bin/env python3
"""公開前的個資檢查：確保雇主名稱、具體持倉等不會被推到公開 repo。零 token。
被 daily pipeline 呼叫，查到就退非 0。"""
import os, re, sys, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BANNED = [r"瑞昱", r"Realtek", r"\bMSTR\b", r"GOOG/BTC", r"BTC 監控", r"phyUD", r"信哥"]
hits = []
for f in glob.glob("**/*.md", recursive=True) + glob.glob("**/*.html", recursive=True) \
       + glob.glob("index/*.txt") + glob.glob("docs/*.json"):
    if f.startswith("corpus/"):
        continue
    t = open(f, encoding="utf-8", errors="replace").read()
    for b in BANNED:
        for m in re.finditer(b, t):
            line = t[:m.start()].count("\n") + 1
            hits.append(f"{f}:{line} → {m.group(0)}")
if hits:
    print(f"[privacy] 發現 {len(hits)} 處個資，不應公開：")
    for h in hits[:20]:
        print("   ", h)
    sys.exit(1)
print("[privacy] 通過：未發現雇主名稱或持倉資訊")
