#!/usr/bin/env python3
"""公開前的個資檢查：確保雇主名稱、具體持倉等不會被推到公開 repo。零 token。
被 daily pipeline 呼叫，查到就退 1，讀不到清單就退 2。

要找的字只放在這台機器的 private_terms.json（見 bin/private_terms.py），
公開 repo 不寫原字。查到時只印檔名、行號和規則編號：這份輸出會進紀錄檔，
也可能被貼到別處。"""
import glob
import os
import sys

from private_terms import PrivateTermsError, load_private_terms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scan(root, banned):
    """回傳 ["檔名:行號 規則 #N", ...]；corpus/ 底下的第三方語料不查。"""
    base = glob.escape(root)
    paths = (glob.glob(os.path.join(base, "**", "*.md"), recursive=True)
             + glob.glob(os.path.join(base, "**", "*.html"), recursive=True)
             + glob.glob(os.path.join(base, "index", "*.txt"))
             + glob.glob(os.path.join(base, "docs", "*.json")))
    hits = []
    for path in paths:
        # Windows 的路徑用 \ 分隔；先換成 /，corpus/ 的排除才會生效
        f = os.path.relpath(path, root).replace(os.sep, "/")
        if f.startswith("corpus/"):
            continue
        with open(path, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        for number, pattern in enumerate(banned, 1):
            for m in pattern.finditer(t):
                line = t[:m.start()].count("\n") + 1
                hits.append(f"{f}:{line} 規則 #{number}")
    return hits


def main():
    try:
        banned, _ = load_private_terms()
    except PrivateTermsError as exc:
        print(f"[privacy] STOP：讀不到個資清單，無法確認能否公開：{exc}")
        return 2
    hits = scan(ROOT, banned)
    if hits:
        print(f"[privacy] 發現 {len(hits)} 處個資，不應公開（只列位置與規則編號）：")
        for h in hits[:20]:
            print("   ", h)
        return 1
    print("[privacy] 通過：未發現雇主名稱或持倉資訊")
    return 0


if __name__ == "__main__":
    sys.exit(main())
