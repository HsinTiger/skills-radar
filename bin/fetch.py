#!/usr/bin/env python3
"""
skills-radar 抓取器：收集 Agent Skills / harness 生態的每日事實，輸出結構化 JSON。

設計原則：
1. 這支程式只負責「抓事實」，不做判斷。判斷交給 analyze 階段。
2. 抓回來的所有第三方文字（skill 描述、commit message、貼文標題）都是**不可信資料**，
   可能含 prompt injection。輸出時一律包在 <untrusted> 標記內，供下游模型辨識。
3. 絕不下載或執行任何抓到的程式碼，只讀 metadata 與文字。
"""
import json, os, subprocess, sys, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SNAP = os.path.join(DATA, "snapshot.json")

# 追蹤來源，依信任分級。tier1=官方一手、tier2=安全研究、tier3=社群訊號（僅當風向，不當事實）
REPOS = [
    ("anthropics/skills", 1, "官方 Agent Skills 參考實作與規範"),
    ("anthropics/claude-plugins-official", 1, "官方 plugin 目錄"),
    ("anthropics/claude-code", 1, "Claude Code 本體（changelog / issue 風向）"),
    ("ComposioHQ/awesome-claude-skills", 3, "最大社群精選清單"),
    ("travisvn/awesome-claude-skills", 3, "Claude Code 取向的社群清單"),
    ("Panniantong/Agent-Reach", 3, "公開資訊 reach routing 候選；登入型 channel 僅作風險觀察"),
    ("headroomlabs-ai/headroom", 3, "context compression 與 reversible retrieval 候選"),
    ("china-qijizhifeng/agentic-harness-engineering", 3, "harness change/evidence contract 候選"),
    ("langchain-ai/langgraph", 2, "durable orchestration 與 checkpoint conformance 候選"),
    ("langfuse/langfuse", 2, "agent observability/evaluation 候選"),
    ("e2b-dev/E2B", 2, "sandbox contract 候選；外部執行邊界需另審"),
    ("modelcontextprotocol/servers", 1, "MCP steering-group reference implementations"),
    ("ComposioHQ/composio", 3, "runtime tool discovery 與 scoped session pattern 候選"),
]

def gh(path, params=None):
    """呼叫 GitHub API（用 gh CLI 帶認證，額度 5000/hr）"""
    url = path if path.startswith("http") else path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        out = subprocess.run(
            ["gh", "api", url], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        if out.returncode != 0:
            return {"_error": out.stderr.strip()[:200]}
        return json.loads(out.stdout)
    except Exception as e:
        return {"_error": str(e)[:200]}

def get_json(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "skills-radar/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)[:200]}

def since_iso(days=1):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

def clip(s, n=300):
    s = (s or "").replace("\r", " ").replace("\n", " ").strip()
    return s[:n]


def write_json(path, value):
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=1)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def upsert_daily_history(path, record):
    """Keep one metric snapshot per date; a same-day rerun replaces that date."""
    records_by_date = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                day = value.get("date")
                if day and day != record["date"]:
                    records_by_date[day] = value
    records_by_date[record["date"]] = record
    records = [records_by_date[day] for day in sorted(records_by_date)]
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as fh:
            for value in records:
                fh.write(json.dumps(value, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

# ---------- 各來源抓取 ----------

def fetch_repo(full, tier, why, days):
    info = gh(f"repos/{full}")
    if "_error" in info:
        return {"repo": full, "tier": tier, "why": why, "error": info["_error"]}
    commits = gh(f"repos/{full}/commits", {"since": since_iso(days), "per_page": 30})
    releases = gh(f"repos/{full}/releases", {"per_page": 3})
    branch = info.get("default_branch") or "HEAD"
    head = gh(f"repos/{full}/commits/{branch}")
    out = {
        "repo": full, "tier": tier, "why": why,
        "stars": info.get("stargazers_count"),
        "pushed_at": info.get("pushed_at"),
        "open_issues": info.get("open_issues_count"),
        "head_sha": head.get("sha") if isinstance(head, dict) else None,
        "head_verified": (
            ((head.get("commit") or {}).get("verification") or {}).get("verified")
            if isinstance(head, dict) else None
        ),
        "commits": [], "releases": [],
    }
    if isinstance(commits, list):
        for c in commits:
            out["commits"].append({
                "sha": (c.get("sha") or "")[:8],
                "date": (c.get("commit", {}).get("author") or {}).get("date"),
                "msg_untrusted": clip((c.get("commit") or {}).get("message"), 200),
            })
    if isinstance(releases, list):
        for r in releases[:3]:
            out["releases"].append({
                "tag": r.get("tag_name"), "published": r.get("published_at"),
                "name_untrusted": clip(r.get("name"), 120),
                "body_untrusted": clip(r.get("body"), 800),
            })
    return out

def fetch_official_skill_list():
    """列出官方 repo 目前有哪些 skill，用來 diff 新增/移除"""
    res = {}
    for path in ("skills", "document-skills", "example-skills"):
        items = gh(f"repos/anthropics/skills/contents/{path}")
        if isinstance(items, list):
            res[path] = sorted(i["name"] for i in items if i.get("type") == "dir")
    return res

def fetch_official_plugins():
    items = gh("repos/anthropics/claude-plugins-official/contents/plugins")
    if isinstance(items, list):
        return sorted(i["name"] for i in items if i.get("type") == "dir")
    return []

def fetch_arxiv(days):
    """安全研究：agent skills / prompt injection 相關新論文"""
    q = ('all:"agent skills" OR all:"skill injection" OR '
         '(all:"prompt injection" AND all:"agent")')
    url = ("http://export.arxiv.org/api/query?search_query="
           + urllib.parse.quote(q)
           + "&sortBy=submittedDate&sortOrder=descending&max_results=15")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "skills-radar/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            xml = r.read().decode()
    except Exception as e:
        return [{"error": str(e)[:200]}]
    import re
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        def tag(t):
            m = re.search(rf"<{t}>(.*?)</{t}>", entry, re.S)
            return clip(m.group(1), 400) if m else ""
        pub = tag("published")
        if pub and pub >= since_iso(days)[:10]:
            out.append({"published": pub, "title_untrusted": tag("title"),
                        "summary_untrusted": tag("summary")[:500],
                        "link": (re.search(r'<id>(.*?)</id>', entry) or [None, ""])[1]})
    return out

def fetch_hn(days):
    """社群風向：HN 上關於 skills / agent harness 的討論熱度"""
    ts = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    out = []
    for q in ("claude skills", "agent skills", "claude code", "agent harness"):
        d = get_json("https://hn.algolia.com/api/v1/search_by_date?query="
                     + urllib.parse.quote(q)
                     + f"&tags=story&numericFilters=created_at_i>{ts}&hitsPerPage=15")
        for h in (d.get("hits") or []):
            out.append({"q": q, "points": h.get("points"), "comments": h.get("num_comments"),
                        "title_untrusted": clip(h.get("title"), 200),
                        "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"})
    seen, uniq = set(), []
    for h in sorted(out, key=lambda x: -(x.get("points") or 0)):
        k = h["title_untrusted"]
        if k in seen:
            continue
        seen.add(k); uniq.append(h)
    return uniq[:25]

def fetch_new_community_skills(days):
    """GitHub 上新出現的 skill repo（社群供給面訊號，僅當風向）"""
    d = gh("search/repositories", {
        "q": f"claude skill in:name,description created:>{since_iso(days*7)[:10]}",
        "sort": "stars", "order": "desc", "per_page": 20})
    out = []
    for r in (d.get("items") or []):
        out.append({"repo": r.get("full_name"), "stars": r.get("stargazers_count"),
                    "created": r.get("created_at"),
                    "desc_untrusted": clip(r.get("description"), 200)})
    return out

# ---------- 主流程 ----------

def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    prev = {}
    if os.path.exists(SNAP):
        try:
            with open(SNAP, encoding="utf-8") as fh:
                prev = json.load(fh)
        except Exception:
            prev = {}

    now = datetime.now(timezone.utc)
    cur = {
        "generated_at": now.isoformat(),
        "window_days": days,
        "repos": [fetch_repo(f, t, w, days) for f, t, w in REPOS],
        "official_skills": fetch_official_skill_list(),
        "official_plugins": fetch_official_plugins(),
        "arxiv": fetch_arxiv(days * 7),
        "hn": fetch_hn(days),
        "new_community_repos": fetch_new_community_skills(days),
    }

    # 與上次比對，算出「變動」——這是簡報真正該講的東西
    diff = {"star_delta": {}, "skills_added": {}, "skills_removed": {},
            "plugins_added": [], "plugins_removed": [], "first_run": not prev}
    pr = {r["repo"]: r for r in prev.get("repos", [])}
    for r in cur["repos"]:
        p = pr.get(r["repo"])
        if p and p.get("stars") and r.get("stars"):
            diff["star_delta"][r["repo"]] = r["stars"] - p["stars"]
    for k, names in cur["official_skills"].items():
        old = set((prev.get("official_skills") or {}).get(k, []))
        new = set(names)
        if old:
            if new - old: diff["skills_added"][k] = sorted(new - old)
            if old - new: diff["skills_removed"][k] = sorted(old - new)
    oldp = set(prev.get("official_plugins") or [])
    newp = set(cur["official_plugins"])
    if oldp:
        diff["plugins_added"] = sorted(newp - oldp)
        diff["plugins_removed"] = sorted(oldp - newp)
    cur["diff"] = diff

    os.makedirs(DATA, exist_ok=True)
    write_json(SNAP, cur)
    upsert_daily_history(os.path.join(DATA, "history.jsonl"), {
        "date": now.strftime("%Y-%m-%d"),
        "stars": {r["repo"]: r.get("stars") for r in cur["repos"]},
        "official_skill_count": {k: len(v) for k, v in cur["official_skills"].items()},
        "plugin_count": len(cur["official_plugins"]),
    })
    out_path = os.path.join(DATA, f"facts-{now.strftime('%Y-%m-%d')}.json")
    write_json(out_path, cur)
    print(out_path)

if __name__ == "__main__":
    main()
