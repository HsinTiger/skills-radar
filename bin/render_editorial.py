#!/usr/bin/env python3
"""Render validated editorial Markdown into safe, dependency-free HTML pages."""

from __future__ import annotations

import argparse
import html
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def inline(text: str) -> str:
    value = html.escape(text, quote=True)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"〔([^〕]+)〕", r'<span class="cite">〔\1〕</span>', value)
    return value


def markdown_body(markdown: str) -> tuple[str, str]:
    title = "Skills Radar 觀點"
    output = []
    paragraph = []
    list_kind = None

    def flush_paragraph():
        if paragraph:
            output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list():
        nonlocal list_kind
        if list_kind:
            output.append(f"</{list_kind}>")
            list_kind = None

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph(); close_list()
            level = len(heading.group(1))
            text = heading.group(2)
            if level == 1:
                title = text
            output.append(f"<h{level}>{inline(text)}</h{level}>")
            continue
        if line.startswith("> "):
            flush_paragraph(); close_list()
            output.append(f"<blockquote>{inline(line[2:])}</blockquote>")
            continue
        item = re.match(r"^[-*]\s+(.+)$", line)
        ordered = re.match(r"^\d+[.)]\s+(.+)$", line)
        if item or ordered:
            flush_paragraph()
            desired = "ol" if ordered else "ul"
            if list_kind != desired:
                close_list()
                output.append(f"<{desired}>")
                list_kind = desired
            output.append(f"<li>{inline((ordered or item).group(1))}</li>")
            continue
        paragraph.append(line)
    flush_paragraph(); close_list()
    return title, "\n".join(output)


def page_html(title: str, body: str, date: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--bg:#fbfaf8;--panel:#fff;--ink:#1c1b19;--dim:#6b6660;--line:#e6e2db;--accent:#a74718}}
@media(prefers-color-scheme:dark){{:root{{--bg:#151413;--panel:#1e1d1b;--ink:#ece8e2;--dim:#aaa29a;--line:#35312d;--accent:#e08050}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;line-height:1.85}}
main{{max-width:760px;margin:auto;padding:2.5rem 1.25rem 5rem}}nav{{font-size:.9rem;margin-bottom:2.5rem}}a{{color:var(--accent)}}h1{{font-size:clamp(2rem,6vw,3.2rem);line-height:1.15;letter-spacing:-.035em}}h2{{margin-top:3rem;border-top:1px solid var(--line);padding-top:1.2rem}}p{{margin:1rem 0}}blockquote{{margin:1.5rem 0;padding:1rem 1.2rem;border-left:4px solid var(--accent);background:var(--panel);color:var(--dim)}}
li{{margin:.55rem 0}}code,.cite{{font-family:ui-monospace,"SF Mono",monospace;font-size:.86em;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:.05rem .28rem}}footer{{margin-top:4rem;color:var(--dim);font-size:.82rem}}
</style></head><body><main><nav><a href="../index.html">← Skills Radar</a> · <a href="index.html">所有觀點</a></nav>
{body}<footer>文章日期：{html.escape(date)} · 由 AI 依可查證資料生成</footer></main></body></html>
"""


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def render_all(source_dir: Path, output_dir: Path) -> list[dict]:
    entries = []
    for source in sorted(source_dir.glob("*.md"), reverse=True):
        date = source.stem
        markdown = source.read_text(encoding="utf-8")
        title, body = markdown_body(markdown)
        write_atomic(output_dir / f"{date}.html", page_html(title, body, date))
        entries.append({"date": date, "title": title, "href": f"{date}.html"})
    links = "\n".join(
        f'<li><a href="{html.escape(item["href"])}">{html.escape(item["title"])}</a></li>'
        for item in entries
    ) or "<li>尚無文章</li>"
    index = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Skills Radar 觀點</title>
<style>body{{max-width:760px;margin:auto;padding:2rem;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",sans-serif;line-height:1.8}}li{{margin:.8rem 0}}a{{color:#a74718}}</style></head>
<body><p><a href="../index.html">← Skills Radar</a></p><h1>Skills Radar 觀點</h1><p>由每日可查證資料生成的產業觀點，不把文件自述當成實際部署。</p><ul>{links}</ul></body></html>"""
    write_atomic(output_dir / "index.html", index)
    return entries


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "research/editorials")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/editorials")
    args = parser.parse_args(argv)
    source = args.source_dir / f"{args.date}.md"
    if not source.is_file():
        raise SystemExit(f"editorial source missing: {source}")
    entries = render_all(args.source_dir, args.output_dir)
    print(f"editorials rendered: {len(entries)}; latest={entries[0]['date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
