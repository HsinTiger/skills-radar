#!/usr/bin/env python3
"""
harvest_eda.py — EDA / IC 設計長尾的分層過取樣。零 token。

方法論（重要）：
這是**刻意的過取樣**，不是中立抽樣。用 EDA/IC 詞彙去撈，撈到的樣本密度遠高於母體真實比例。
因此每一筆都標記 `sample: "targeted-eda"`，統計整體比例時**必須排除**，
否則「硬體/EDA 佔 0.67%」這個數字會被自己污染成假的。

中立樣本（sample 缺值或 "neutral"）→ 用來估比例
過取樣樣本（targeted-eda）→ 只用來分析 EDA 內部結構：誰在做、做什麼層級、卡在哪

這是分層抽樣的標準做法：稀有層過取樣以取得足夠的層內統計力，同時保留原始權重資訊。
"""
import json, os, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("hc", os.path.join(ROOT, "bin", "harvest_corpus.py"))
hc = importlib.util.module_from_spec(spec); spec.loader.exec_module(hc)

CORPUS = os.path.join(ROOT, "corpus")
SEEN = os.path.join(CORPUS, "seen.tsv")
MASTER = os.path.join(CORPUS, "master.jsonl")

# 詞彙分三層：核心晶片設計 / 驗證 / 鄰接硬體。分開記錄，之後可分辨樣本來自哪一層。
VOCAB = {
    "chip-design": ["verilog", "systemverilog", "RTL", "netlist", "tapeout", "ASIC",
                    "synthesis", "floorplan", "placement routing", "standard cell",
                    "timing closure", "STA", "PDK", "OpenLane", "OpenROAD", "yosys",
                    "magic VLSI", "klayout", "innovus", "design compiler"],
    "verification": ["UVM", "testbench", "cocotb", "SVA assertion", "functional coverage",
                     "constrained random", "verilator", "waveform debug", "VCD",
                     "regression test RTL", "formal verification hardware", "code coverage RTL"],
    "adjacent-hw": ["FPGA", "vivado", "quartus", "SoC", "AXI", "AMBA", "embedded HDL",
                    "hardware description", "chisel scala", "SpinalHDL", "MLIR CIRCT",
                    "RISC-V core", "DDR PHY", "SerDes", "analog layout", "SPICE simulation"],
}
PER_REPO_CAP = 10

def load_seen():
    s = set()
    if os.path.exists(SEEN):
        for line in open(SEEN, encoding="utf-8", errors="replace"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2:
                s.add((p[0], p[1]))
    return s

def search(term, tier, found, tiers):
    q = urllib.parse.quote(f"filename:SKILL.md {term}")
    for page in range(1, 11):
        d = hc.gh(f"search/code?q={q}&per_page=100&page={page}")
        time.sleep(2.2)
        items = (d.get("items") or []) if isinstance(d, dict) else []
        if not items:
            break
        for it in items:
            repo = (it.get("repository") or {}).get("full_name")
            path = it.get("path")
            if not repo or not path:
                continue
            found.setdefault(repo, set())
            if len(found[repo]) < PER_REPO_CAP:
                found[repo].add(path)
                tiers.setdefault((repo, path), set()).add(tier)
                tiers[(repo, path)].add("term:" + term)
        if len(items) < 100:
            break

def main():
    seen = load_seen()
    found, tiers = {}, {}
    total_terms = sum(len(v) for v in VOCAB.values())
    i = 0
    for tier, terms in VOCAB.items():
        for t in terms:
            i += 1
            search(t, tier, found, tiers)
            print(f"  [{i}/{total_terms}] {tier}/{t} → 累計 "
                  f"{sum(len(v) for v in found.values())} 筆", file=sys.stderr)

    targets = [(r, p) for r, ps in found.items() for p in ps if (r, p) not in seen]
    print(f"[eda] 掃到 {sum(len(v) for v in found.values())} 筆，新的 {len(targets)} 筆", file=sys.stderr)
    if not targets:
        return

    repos = sorted({r for r, _ in targets})
    meta = {}
    def rmeta(r):
        d = hc.gh(f"repos/{r}")
        if isinstance(d, dict) and "_error" not in d:
            meta[r] = {"stars": d.get("stargazers_count"), "created": d.get("created_at"),
                       "topics": d.get("topics") or [], "lang": d.get("language"),
                       "owner_type": (d.get("owner") or {}).get("type")}
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(rmeta, repos))

    rows, done = [], [0]
    def work(t):
        repo, path = t
        txt = hc.fetch_raw(repo, path)
        done[0] += 1
        if done[0] % 200 == 0:
            print(f"    內容 {done[0]}/{len(targets)}", file=sys.stderr)
        if not txt or len(txt) < 40:
            return None
        p = hc.parse_skill(txt)
        m = meta.get(repo, {})
        tg = sorted(tiers.get((repo, path), []))
        return {"repo": repo, "path": path, "stars": m.get("stars"),
                "repo_created": m.get("created"), "repo_topics": m.get("topics"),
                "repo_lang": m.get("lang"), "owner_type": m.get("owner_type"),
                "chars": len(txt), "sample": "targeted-eda",
                "eda_tier": [x for x in tg if not x.startswith("term:")],
                "matched_terms": [x[5:] for x in tg if x.startswith("term:")],
                "first_seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"), **p}
    with ThreadPoolExecutor(max_workers=14) as ex:
        for r in ex.map(work, targets):
            if r and (r["name"] or r["description"]):
                rows.append(r)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = os.path.join(CORPUS, f"eda-{stamp}.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(MASTER, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SEEN, "a", encoding="utf-8") as fh:
        for r, p in targets:
            fh.write(f"{r}\t{p}\n")
    print(f"[eda] 新增 {len(rows)} 筆 → {out}", file=sys.stderr)
    print(out)

if __name__ == "__main__":
    main()
