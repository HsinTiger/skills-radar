#!/usr/bin/env python3
"""
eda_deepdive.py — EDA / IC 設計長尾的內部結構分析。零 token。

只在這裡使用過取樣樣本（sample=targeted-eda）。目的不是估比例，
而是回答中立樣本因為樣本太小（36 件）答不了的問題：
  - 硬體圈裡誰在寫 skill？做的是哪一層的工作？
  - 「真晶片設計」與「只是提到 FPGA 的嵌入式專案」比例如何？
  - 驗證（verify）在這個領域到底有沒有被做起來？
  - 哪些痛點反覆出現＝這個行業的通則，而不是個案？
"""
import json, os, re
from collections import Counter, defaultdict
from statistics import median

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, "corpus", "master.jsonl")

rows = []
for line in open(MASTER, encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line:
        continue
    try:
        rows.append(json.loads(line))
    except Exception:
        pass

# 判定硬體樣本一律用「模型/LLM 標的 domain」，不用關鍵字正則。
# 教訓：關鍵字正則的誤判率實測 75.6%——RTL 在網頁開發是 right-to-left、STA/timing closure 也大量誤中。
CONF_MIN = 0.6
eda = [r for r in rows if r.get("domain") == "hardware-eda"
       and (r.get("label_source") != "model" or (r.get("domain_conf") or 0) >= CONF_MIN)]
neutral_all = [r for r in rows if r.get("sample") != "targeted-eda" and r.get("domain")]

# 依詞彙層級判斷「有多真」——被 chip-design 層撈到且內容確實談 RTL/時序，才算核心
CORE = re.compile(r"\b(verilog|systemverilog|rtl|netlist|tapeout|asic|synthes|floorplan|"
                  r"place\s*(and|&)?\s*rout|standard\s*cell|timing\s*(closure|constraint)|"
                  r"\bsta\b|pdk|openlane|openroad|yosys|innovus|design\s*compiler)\b", re.I)
VERIF = re.compile(r"\b(uvm|testbench|cocotb|assertion|functional\s*coverage|"
                   r"constrained\s*random|verilator|waveform|\bvcd\b|regression)\b", re.I)

def blob(r):
    return " ".join([r.get("name") or "", r.get("description") or "",
                     (r.get("body_head") or "")[:800], " ".join(r.get("matched_terms") or [])])

# 分層仍用關鍵字，但只在「已確認是硬體」的樣本內部分層，誤判影響大幅降低
core, verif, adjacent = [], [], []
for r in eda:
    b = blob(r)
    if CORE.search(b):
        core.append(r)
    elif VERIF.search(b):
        verif.append(r)
    else:
        adjacent.append(r)

def profile(rs, label):
    if not rs:
        return {"label": label, "n": 0}
    tc = Counter(x.get("task") for x in rs if x.get("task"))
    mc = Counter(x.get("maturity") for x in rs if x.get("maturity"))
    pc = Counter((x.get("profession") or "unknown") for x in rs)
    stars = [x.get("stars") or 0 for x in rs]
    n_task = sum(tc.values()) or 1
    n_mat = sum(mc.values()) or 1
    return {
        "label": label, "n": len(rs),
        "task_pct": {k: round(100 * v / n_task, 1) for k, v in tc.most_common()},
        "maturity_pct": {k: round(100 * v / n_mat, 1) for k, v in mc.most_common()},
        "top_professions": dict(pc.most_common(10)),
        "median_stars": int(median(stars)) if stars else 0,
        "verify_pct": round(100 * tc.get("verify", 0) / n_task, 1),
        "production_pct": round(100 * mc.get("production", 0) / n_mat, 1),
    }

# 全體基準（只用中立樣本）
gt = Counter(r.get("task") for r in neutral_all if r.get("task"))
gm = Counter(r.get("maturity") for r in neutral_all if r.get("maturity"))
gn_t, gn_m = sum(gt.values()) or 1, sum(gm.values()) or 1

# 反覆出現的痛點＝行業通則
def pain_themes(rs):
    THEMES = {
        "驗證與回歸": r"驗證|測試|覆蓋率|回歸|testbench|uvm|assert",
        "波形與除錯": r"波形|除錯|debug|waveform|vcd|trace",
        "時序與收斂": r"時序|timing|收斂|clock|延遲|constraint",
        "工具鏈與環境": r"工具鏈|環境|安裝|設定|configure|toolchain|licence|license",
        "程式碼生成": r"生成|產生|撰寫|generate|scaffold|模板|template",
        "規格與文件": r"規格|文件|spec|document|需求",
        "合成與實作": r"合成|synthes|佈局|佈線|place|rout|floorplan|layout",
        "跨工具轉換": r"轉換|convert|轉譯|translat|格式",
    }
    c = Counter()
    for r in rs:
        p = (r.get("pain") or "") + " " + (r.get("name") or "")
        for k, pat in THEMES.items():
            if re.search(pat, p, re.I):
                c[k] += 1
    return dict(c.most_common())

out = {
    "n_eda_total": len(eda),
    "n_targeted": sum(1 for r in eda if r.get("sample") == "targeted-eda"),
    "conf_min": CONF_MIN,
    "n_llm_labeled": sum(1 for r in eda if r.get("label_source") != "model"),
    "n_neutral": sum(1 for r in eda if r.get("sample") != "targeted-eda"),
    "global_baseline": {
        "task_pct": {k: round(100 * v / gn_t, 1) for k, v in gt.most_common()},
        "production_pct": round(100 * gm.get("production", 0) / gn_m, 1),
        "verify_pct": round(100 * gt.get("verify", 0) / gn_t, 1),
    },
    "layers": [profile(core, "核心晶片設計"), profile(verif, "驗證"), profile(adjacent, "鄰接硬體")],
    "pain_themes": {"核心晶片設計": pain_themes(core), "驗證": pain_themes(verif),
                    "鄰接硬體": pain_themes(adjacent)},
    "top_core": [{"repo": r.get("repo"), "stars": r.get("stars"), "name": (r.get("name") or "")[:90],
                  "task": r.get("task"), "maturity": r.get("maturity"),
                  "pain": r.get("pain"), "terms": (r.get("matched_terms") or [])[:4]}
                 for r in sorted(core, key=lambda x: -(x.get("stars") or 0))[:30]],
    "top_verif": [{"repo": r.get("repo"), "stars": r.get("stars"), "name": (r.get("name") or "")[:90],
                   "task": r.get("task"), "maturity": r.get("maturity"), "pain": r.get("pain")}
                  for r in sorted(verif, key=lambda x: -(x.get("stars") or 0))[:25]],
}
json.dump(out, open(os.path.join(ROOT, "corpus", "eda_deepdive.json"), "w"),
          ensure_ascii=False, indent=1)

print(f"EDA 深度分析：{out['n_eda_total']} 件"
      f"（過取樣 {out['n_targeted']}、中立 {out['n_neutral']}）")
print(f"全體基準：verify {out['global_baseline']['verify_pct']}%、"
      f"production {out['global_baseline']['production_pct']}%\n")
for L in out["layers"]:
    if L["n"]:
        print(f"  {L['label']:8s} n={L['n']:5d}  verify {L['verify_pct']:5.1f}%  "
              f"production {L['production_pct']:5.1f}%  中位星 {L['median_stars']}")
print("\n痛點主題（核心晶片設計）:")
for k, v in list(out["pain_themes"]["核心晶片設計"].items())[:8]:
    print(f"   {k:12s} {v}")
