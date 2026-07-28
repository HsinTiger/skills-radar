#!/usr/bin/env python3
"""
harvest_corpus.py — 蒐集公開 SKILL.md 語料，作為「開發者行為」研究的原始資料。

研究前提：一個人自願把某件工作寫成 skill 並公開，代表 (a) 那件事夠痛 (b) 他真的在用 AI 做。
所以這份語料是一種揭露性偏好（revealed preference）資料，比問卷或新聞可信。

取樣策略（重要）：
- 用中立軸（檔案大小分層 + 建立時間）分層抽樣，**不預設職業類別去搜**，
  否則只會撈到自己的假設。分類留給後續階段，從資料長出來。
- 每個 repo 最多取 N 個 skill，避免單一大型 repo（或其 fork）灌爆分佈。
- 只讀文字 metadata，不下載、不執行任何程式碼。
"""
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "corpus")
os.makedirs(OUT, exist_ok=True)

PER_REPO_CAP = 6
SIZE_BUCKETS = [
    "<1000", "1000..2000", "2000..3000", "3000..4500", "4500..6000",
    "6000..8000", "8000..12000", "12000..20000", ">20000",
]

def gh(path):
    for attempt in range(4):
        r = subprocess.run(
            ["gh", "api", path], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90,
        )
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except Exception as exc:
                return {"_error": f"invalid gh JSON: {exc}"}
        if "rate limit" in r.stderr.lower() or "403" in r.stderr:
            time.sleep(20 * (attempt + 1))
            continue
        return {"_error": r.stderr.strip()[:160]}
    return {"_error": "retry exhausted"}

def search_path(bucket, page):
    query = urllib.parse.urlencode({
        "q": f"filename:SKILL.md size:{bucket}",
        "per_page": 100,
        "page": page,
    })
    return f"search/code?{query}"

def search_skill_files():
    """分層抽樣：對每個大小級距翻頁，取得跨領域的 SKILL.md 清單"""
    found = {}
    for bucket in SIZE_BUCKETS:
        for page in range(1, 11):          # code search 上限 1000 筆/query
            d = gh(search_path(bucket, page))
            if "_error" in d:
                raise RuntimeError(f"GitHub code search failed for bucket={bucket} page={page}: {d['_error']}")
            if "items" not in d:
                raise RuntimeError(f"GitHub code search returned no items field for bucket={bucket} page={page}")
            items = d.get("items") or []
            if not items:
                break
            for it in items:
                repo = (it.get("repository") or {}).get("full_name")
                path = it.get("path")
                if not repo or not path:
                    continue
                found.setdefault(repo, [])
                if len(found[repo]) < PER_REPO_CAP and path not in found[repo]:
                    found[repo].append(path)
            print(f"  bucket {bucket} page {page}: 累計 {sum(len(v) for v in found.values())} 檔 / {len(found)} repo",
                  file=sys.stderr)
            time.sleep(6.5)                 # code search 限 30 req/min
            if len(items) < 100:
                break
    if not found:
        raise RuntimeError("GitHub code search completed without any SKILL.md results")
    return found

def fetch_raw(repo, path):
    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{urllib.request.quote(path)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "skills-radar-research/1.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            continue
    return None

def parse_skill(text):
    """抽出 frontmatter 的 name/description，以及正文開頭。全部視為不可信文字。"""
    name = desc = ""
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if m:
        fm, body = m.group(1), m.group(2)
        n = re.search(r"^name:\s*(.+)$", fm, re.M)
        d = re.search(r"^description:\s*(.+?)(?=\n[a-zA-Z_-]+:|\Z)", fm, re.M | re.S)
        name = (n.group(1).strip().strip('"\'') if n else "")
        desc = re.sub(r"\s+", " ", d.group(1).strip().strip('"\'')) if d else ""
    if not name:
        h = re.search(r"^#\s+(.+)$", body, re.M)
        name = h.group(1).strip() if h else ""
    body_clip = re.sub(r"\s+", " ", body)[:900]
    # 記錄它宣稱會用到哪些能力 —— 這反映「開發者要 AI 做什麼層級的事」
    tools = sorted(set(re.findall(
        r"\b(bash|shell|python|node|curl|git|docker|kubectl|sql|api|browser|playwright|selenium|"
        r"pandas|ffmpeg|latex|excel|pdf|figma|slack|jira|notion|aws|gcp|azure|terraform)\b",
        text.lower())))
    return {"name": name[:160], "description": desc[:600], "body_head": body_clip, "tools_hinted": tools}

def main():
    print("[1/3] 搜尋 SKILL.md（分層抽樣）...", file=sys.stderr)
    found = search_skill_files()
    targets = [(r, p) for r, ps in found.items() for p in ps]
    print(f"    → {len(targets)} 個檔案 / {len(found)} 個 repo", file=sys.stderr)

    print("[2/3] 補 repo metadata...", file=sys.stderr)
    repos = list(found.keys())
    meta = {}
    def rmeta(r):
        d = gh(f"repos/{r}")
        if "_error" not in d:
            meta[r] = {"stars": d.get("stargazers_count"), "created": d.get("created_at"),
                       "pushed": d.get("pushed_at"), "topics": d.get("topics") or [],
                       "desc_untrusted": (d.get("description") or "")[:300],
                       "owner_type": (d.get("owner") or {}).get("type")}
    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(rmeta, repos))

    print("[3/3] 抓取 SKILL.md 內容...", file=sys.stderr)
    rows, done = [], [0]
    def work(t):
        repo, path = t
        txt = fetch_raw(repo, path)
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"    {done[0]}/{len(targets)}", file=sys.stderr)
        if not txt or len(txt) < 40:
            return None
        p = parse_skill(txt)
        m = meta.get(repo, {})
        return {"repo": repo, "path": path, "stars": m.get("stars"),
                "repo_created": m.get("created"), "repo_topics": m.get("topics"),
                "owner_type": m.get("owner_type"), "chars": len(txt), **p}
    with ThreadPoolExecutor(max_workers=12) as ex:
        for r in ex.map(work, targets):
            if r and (r["name"] or r["description"]):
                rows.append(r)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = os.path.join(OUT, f"skills-{stamp}.jsonl")
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"完成：{len(rows)} 筆 → {out}", file=sys.stderr)
    print(out)

if __name__ == "__main__":
    main()
