#!/usr/bin/env python3
"""重建 README.md：最新一期摘要 + 歷史索引 + 生態指標趨勢"""
import os, json, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

dailies = sorted(glob.glob("daily/*.md"), reverse=True)
hist = []
if os.path.exists("data/history.jsonl"):
    for line in open("data/history.jsonl"):
        try:
            hist.append(json.loads(line))
        except Exception:
            pass

latest_block = ""
if dailies:
    t = open(dailies[0], encoding="utf-8").read()
    m = re.search(r"## 今日一句話\s*\n+(.+?)(\n##|\Z)", t, re.S)
    one = m.group(1).strip() if m else ""
    m2 = re.search(r"### 短期（一週內）\s*\n+(.*?)(\n###|\n##|\Z)", t, re.S)
    short = m2.group(1).strip() if m2 else ""
    latest_block = (f"## 最新一期：[{os.path.basename(dailies[0])[:-3]}]({dailies[0]})\n\n"
                    f"**今日一句話**：{one}\n\n**短期建議（一週內）**\n\n{short}\n")

trend = ""
if len(hist) >= 2:
    a, b = hist[-1], hist[0]
    rows = ["| repo | 目前 star | 自 %s 起變化 |" % b["date"], "|---|---:|---:|"]
    for k, v in (a.get("stars") or {}).items():
        old = (b.get("stars") or {}).get(k)
        if v and old:
            rows.append(f"| {k} | {v:,} | {v-old:+,} |")
    trend = "## 生態指標\n\n" + "\n".join(rows) + "\n"
elif hist:
    a = hist[-1]
    rows = ["| repo | star |", "|---|---:|"] + [
        f"| {k} | {v:,} |" for k, v in (a.get("stars") or {}).items() if v]
    trend = "## 生態指標（首次快照）\n\n" + "\n".join(rows) + "\n"

index = "## 歷史簡報\n\n" + "\n".join(
    f"- [{os.path.basename(d)[:-3]}]({d})" for d in dailies[:60]) if dailies else ""

readme = f"""# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

{latest_block}
{trend}
## 這個系統怎麼運作

```
bin/fetch.py        抓事實（GitHub API / arXiv / HN），不做判斷
                    → 第三方文字一律標記 _untrusted，供下游模型辨識
index/prompt_daily.txt  分析規格（含 prompt injection 防禦指令）
bin/run_daily.sh    主流程：抓取 → agy 產簡報 → 驗收 → 更新 README → push
bin/build_readme.py 重建本頁
data/snapshot.json  上次狀態（用於 diff 出「今天有什麼變了」）
data/history.jsonl  指標時序
daily/YYYY-MM-DD.md 每日簡報
```

排程：launchd `com.hsin.skills-radar`，每日 08:30 執行。
手動跑一次：`~/skills-radar/bin/run_daily.sh`

{index}
"""
open("README.md", "w", encoding="utf-8").write(readme)
print(f"README 重建：{len(dailies)} 期簡報")
