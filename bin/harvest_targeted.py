#!/usr/bin/env python3
"""
harvest_targeted.py — 針對指定主題的分層過取樣（一般化版，取代 harvest_eda.py）。零 token。

方法論同 harvest_eda.py：這是**刻意過取樣**，樣本密度遠高於母體。
每筆標記 sample="targeted-<topic>"，統計整體比例時一律排除，只用於該主題的內部結構分析。

用法:
  harvest_targeted.py wifi           只跑 wifi 主題
  harvest_targeted.py wifi eda2      跑多個主題
  harvest_targeted.py --list         列出可用主題

搜尋詞的教訓（EDA 那輪學到的）：
詞太短或太通用會嚴重誤中——`RTL` 在網頁開發是 right-to-left、`STA`/`PA`/`HT` 也是。
所以詞表盡量用複合詞或不易撞名的專有名詞，並在分類階段用模型 domain 標籤把關，不靠關鍵字判定領域。
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
PER_REPO_CAP = 10

TOPICS = {
    # 無線通訊 / WiFi baseband —— 對應使用者本業
    "wifi": {
        "phy-baseband": [
            "802.11 PHY", "WiFi 6", "WiFi 7", "802.11ax", "802.11be", "802.11ac",
            "OFDMA scheduling", "MU-MIMO", "beamforming", "channel estimation",
            "LDPC decoder", "constellation demapper", "carrier frequency offset",
            "PPDU", "preamble detection", "EVM measurement",
        ],
        "mac-protocol": [
            "CSMA/CA", "RTS CTS", "A-MPDU", "target wake time", "hostapd",
            "wpa_supplicant", "802.11 MAC layer", "roaming 802.11r", "WMM QoS",
        ],
        "rf-test": [
            "RF frontend design", "low noise amplifier", "S-parameter", "vector network analyzer",
            "spectrum analyzer automation", "path loss model", "antenna matching",
            "iperf throughput", "wireshark 802.11", "packet sniffer wireless",
        ],
        "other-wireless": [
            "BLE GATT", "Bluetooth mesh", "LoRaWAN", "Zigbee", "5G NR", "LTE physical layer",
            "software defined radio", "GNU Radio", "mmWave", "sub-6 GHz",
        ],
    },
    # EDA 補充面向 —— 第一輪沒撈到的，特別是對應 transform 缺口的規格/暫存器/DFT
    "eda2": {
        "spec-registers": [
            "IP-XACT", "register map generation", "SystemRDL", "register description file",
            "CSR generation", "memory map generation", "peripheral register spec",
        ],
        "dft-test": [
            "design for test", "scan chain", "ATPG", "JTAG boundary scan",
            "MBIST", "fault coverage", "test pattern generation",
        ],
        "quality-checks": [
            "clock domain crossing", "CDC analysis", "RTL lint", "linting SystemVerilog",
            "equivalence checking", "DRC LVS", "physical verification",
            "power analysis RTL", "UPF power intent",
        ],
        "flow-tooling": [
            "Makefile simulation flow", "regression waveform", "FSDB", "coverage merge",
            "Synopsys VCS", "Cadence Xcelium", "Questa simulation", "GTKWave",
        ],
    },
}

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
        time.sleep(6.5)          # code search 實測上限 10 次/分鐘
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

def run_topic(topic):
    vocab = TOPICS[topic]
    seen = load_seen()
    found, tiers = {}, {}
    terms = [(tier, t) for tier, ts in vocab.items() for t in ts]
    for i, (tier, t) in enumerate(terms, 1):
        search(t, tier, found, tiers)
        print(f"  [{topic} {i}/{len(terms)}] {tier}/{t} → 累計 "
              f"{sum(len(v) for v in found.values())}", file=sys.stderr)

    targets = [(r, p) for r, ps in found.items() for p in ps if (r, p) not in seen]
    print(f"[{topic}] 掃到 {sum(len(v) for v in found.values())}，新的 {len(targets)}", file=sys.stderr)
    if not targets:
        return 0

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
        if done[0] % 300 == 0:
            print(f"    內容 {done[0]}/{len(targets)}", file=sys.stderr)
        if not txt or len(txt) < 40:
            return None
        p = hc.parse_skill(txt)
        m = meta.get(repo, {})
        tg = sorted(tiers.get((repo, path), []))
        return {"repo": repo, "path": path, "stars": m.get("stars"),
                "repo_created": m.get("created"), "repo_topics": m.get("topics"),
                "repo_lang": m.get("lang"), "owner_type": m.get("owner_type"),
                "chars": len(txt), "sample": f"targeted-{topic}",
                "topic_tier": [x for x in tg if not x.startswith("term:")],
                "matched_terms": [x[5:] for x in tg if x.startswith("term:")],
                "first_seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"), **p}
    with ThreadPoolExecutor(max_workers=14) as ex:
        for r in ex.map(work, targets):
            if r and (r["name"] or r["description"]):
                rows.append(r)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = os.path.join(CORPUS, f"{topic}-{stamp}.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(MASTER, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(SEEN, "a", encoding="utf-8") as fh:
        for r, p in targets:
            fh.write(f"{r}\t{p}\n")
    print(f"[{topic}] 新增 {len(rows)} 筆 → {out}", file=sys.stderr)
    return len(rows)

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--list":
        for k, v in TOPICS.items():
            print(f"{k}: {sum(len(x) for x in v.values())} 詞 / {len(v)} 層")
        sys.exit(0)
    total = 0
    for topic in args:
        if topic not in TOPICS:
            print(f"未知主題 {topic}", file=sys.stderr); continue
        total += run_topic(topic)
    print(f"合計新增 {total} 筆", file=sys.stderr)
