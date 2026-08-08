#!/usr/bin/env python3
"""站台共用外殼：頂欄導覽與樣式連結。

前端拆成多頁之後，每個 builder（首頁、專區、每日觀點、建議清單、Wiki）
都要吐出同一組導覽與同一份樣式，否則使用者一點進子頁就沒有回頭路。
這支模組是那組標記的唯一來源。
"""
from __future__ import annotations

import html as _html

# (相對路徑, 顯示名稱, 識別碼)
ANALYSIS = [
    ("index.html", "概覽", "home"),
    ("trends.html", "趨勢", "trends"),
    ("niches.html", "缺口", "niches"),
    ("security.html", "安全掃描", "security"),
    ("method.html", "方法", "method"),
]
ZONES = [
    ("eda-ic/", "EDA／IC", "eda-ic"),
    ("investing/", "投資研究", "investing"),
    ("ai-automation/", "AI Harness", "ai-automation"),
]
DOCS = [
    ("editorials/", "每日觀點", "editorials"),
    ("recommendations/", "建議清單", "recommendations"),
    ("wiki/", "Domain Wiki", "wiki"),
]


def _links(items, base: str, current: str) -> str:
    out = []
    for href, label, key in items:
        cur = ' aria-current="page"' if key == current else ""
        out.append(f'<a href="{_html.escape(base)}{_html.escape(href)}"{cur}>{_html.escape(label)}</a>')
    return "".join(out)


def head_links(base: str) -> str:
    """給 <head> 用的樣式連結。base 是回到 docs/ 根目錄的相對前綴。"""
    return f'<link rel="stylesheet" href="{_html.escape(base)}assets/radar.css">'


def topbar(base: str, current: str = "") -> str:
    """全站一致的頂欄。current 傳頁面識別碼即可標成目前位置。"""
    return (
        '<div class="topbar"><div class="wrap">'
        f'<a class="brand" href="{_html.escape(base)}index.html">Skills<span>·</span>Radar</a>'
        '<div class="navscroll"><nav class="main">'
        + _links(ANALYSIS, base, current)
        + '<span class="sep"></span><span class="grp">專區</span>'
        + _links(ZONES, base, current)
        + '<span class="sep"></span><span class="grp">文章</span>'
        + _links(DOCS, base, current)
        + "</nav></div></div></div>"
    )
