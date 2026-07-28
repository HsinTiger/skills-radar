#!/usr/bin/env python3
"""重建 README.md：最新一期摘要 + 歷史索引 + 生態指標趨勢"""
import os, json, glob, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def web_path(path):
    return path.replace(os.sep, "/")

dailies = sorted(glob.glob("daily/*.md"), reverse=True)
recommendations = sorted(glob.glob("research/recommendations/*.md"), reverse=True)
editorials = sorted(glob.glob("research/editorials/*.md"), reverse=True)
eda_zones = sorted(glob.glob("research/zones/eda-ic/*.md"), reverse=True)
investing_zones = sorted(glob.glob("research/zones/investing/*.md"), reverse=True)
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
    latest_block = (f"## 最新一期：[{os.path.basename(dailies[0])[:-3]}]({web_path(dailies[0])})\n\n"
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
    f"- [{os.path.basename(d)[:-3]}]({web_path(d)})" for d in dailies[:60]) if dailies else ""

latest_date = os.path.basename(dailies[0])[:-3] if dailies else "UNKNOWN"
latest_recommendation = recommendations[0] if recommendations else None
recommendation_line = (
    f"- [每日 EDA_IC／財經投資研究 Skill 建議]({web_path(latest_recommendation)})：\n"
    "  每日 08:30 以 deterministic gate 更新；`pilot` 只代表可進入隔離評估，不代表已安裝、已上線或通過正確性驗證。"
    if latest_recommendation else
    "- 每日 EDA_IC／財經投資研究 Skill 建議尚未產生。"
)
editorial_line = (
    f"- [每日觀點文章]({web_path(editorials[0])})：\n"
    "  以當日 corpus manifest、四尺度 evidence、EDA_IC 與財經研究清單生成；包含核心主張、反方觀點與證偽條件。"
    if editorials else
    "- 每日觀點文章尚未產生。"
)
editorial_index = "\n".join(
    f"- [{os.path.basename(e)[:-3]}]({web_path(e)})" for e in editorials[:60]
) if editorials else "尚無文章。"

readme = f"""# Skills Radar

每日追蹤 **Agent Skills / AI harness 生態**的變動，產出短期（一週）、中期（一月）、長期（一季）的策略建議，
以及「哪些 skill 值得跟進、安裝前該驗什麼」。

> ⚠️ **這個 repo 追蹤的生態本身不安全。** Snyk 2026-02 的 ToxicSkills 研究掃描 3,984 個公開 agent skill，
> 發現 **36.82% 含安全缺陷、13.4% 為 critical、76 個確認惡意負載**。
> 本 radar 的推薦一律附信任分級與驗證步驟，**任何 skill 都不要看到就裝**。
> 判斷方法見 [TRUST_MODEL.md](TRUST_MODEL.md)，來源分級見 [SOURCES.md](SOURCES.md)。

{latest_block}
{trend}
## 專題研究

{editorial_line}
{recommendation_line}
- [EDA／數位 IC 設計專區]({web_path(eda_zones[0]) if eda_zones else 'docs/eda-ic/index.html'})：
  逐 skill dossier、日／週／月／季 AI 觀點，以及 WiFi baseband ASIC automation 建置路線；排除 FPGA／embedded／PCB／analog-RF。
- [財經投資研究專區]({web_path(investing_zones[0]) if investing_zones else 'docs/investing/index.html'})：
  逐 skill 研究 gate 與多週期觀點；只做可追溯、可重算研究，不連帳戶、不下單。
- 日／週／月／季觀點：每天早上由同一個排程補齊尚未完成的週期；正文以繁中短篇文章呈現，
  數據依據收在可展開區塊。沒有完整資料就明說不足，不用空值硬湊結論。
- [WiFi ASIC RTL / EDA Skill 適用性研究（2026-07-27）](research/ASIC_WIFI_SKILL_FIT_2026-07-27.md)：
  排除 FPGA、embedded、board/PCB、analog/RF；canonical corpus 與 candidate catalog 已 CURRENT，
  但 secondary taxonomy golden validation 仍為 `BLOCKED`，因此只可作候選路由，不是 EDA runtime proof。

## 這個系統怎麼運作

```
bin/fetch.py        抓事實（GitHub API / arXiv / HN），不做判斷
                    → 第三方文字一律標記 _untrusted，供下游模型辨識
index/prompt_daily.txt  分析規格（含 prompt injection 防禦指令）
bin/run_daily.sh    主流程：抓取 → AI provider 產簡報 → 驗收 → 更新 README → push
bin/build_readme.py 重建本頁
bin/wiki_ingest.py 累積各領域 evidence snapshot，產生 research/wiki 與 docs/wiki 實體頁面
bin/wiki_query.py  查詢最新 Wiki snapshot（不讀第三方原文）
bin/build_daily_recommendations.py  產生 EDA_IC／財經投資研究的每日採用候選、摘要與風險 gate
bin/build_domain_zones.py  建立兩個獨立專區、逐 skill dossier、多週期文章與個人化採用路線
bin/timescale_summaries.py  日／週／月／季 evidence、AI summary、完整期與 catch-up dispatcher
bin/update_corpus.py  區分 collector FAILED、有效零增量與真實新增，寫入 corpus update manifest
bin/build_editorial_evidence.py  組合每日觀點的 source-bounded evidence ledger
bin/render_editorial.py  將通過 citation/no-trade 驗收的 Markdown 安全轉成 HTML
bin/build_corpus_snapshot.py  驗證並壓縮 canonical corpus，產生 Release manifest
bin/write_pipeline_health.py  公開最後一次本機 gate 狀態；remote/Pages 仍須另做 readback
bin/install_launchd.sh  在 canonical Mac 安裝/重載每日 08:30 dispatcher
bin/check_launchd.sh  驗證版本化 plist 契約與 launchd registration
bin/check_published_freshness.py  GitHub Actions 每日 09:30 回讀 live Pages，讓漏跑／stale／部署漂移明確失敗
data/snapshot.json  上次狀態（用於 diff 出「今天有什麼變了」）
data/wiki_history.json Wiki 的 append-only evidence history（同日修正需 revision note）
data/history.jsonl  指標時序
daily/YYYY-MM-DD.md 每日簡報
research/editorials/YYYY-MM-DD.md 每日繁中觀點文章
```

排程：launchd `com.hsin.skills-radar` 每日 08:30 執行 dispatcher；日摘要每天、週摘要每週一、
月摘要每月一日、季摘要每季首月一日更新上一完整期。離線後補跑缺少的 `period_id`。
Mac 首次準備：`python3 -m pip install -r requirements-ml.txt`；安裝或重載：`./bin/install_launchd.sh`；
稽核：`./bin/check_launchd.sh`。安裝器會確認 GitHub 登入、Python 套件及文章模型均可從排程環境找到。
自 2026-07-29 起，09:30 watchdog 另要求 health marker 的 `execution_context=launchd`；人工補跑不算排程證明。
手動跑一次：`~/skills-radar/bin/run_daily.sh`

{index}

## 每日觀點文章

{editorial_index}
"""
open("README.md", "w", encoding="utf-8").write(readme)
print(f"README 重建：{len(dailies)} 期簡報")
