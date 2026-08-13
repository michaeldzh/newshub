#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 AI 资讯生成器（仓库内自包含版本，OpenAI 兼容网关 + 解耦搜索）

- 通过可配置的搜索源检索「过去 24 小时」全球 AI 动态：
    Tavily（设 TAVILY_API_KEY 时优先） -> 否则免 key 的 Google News RSS + Hacker News -> 最后 DDG 兜底
- 将检索结果作为上下文交给 LLM（OpenAI Chat Completions 格式）总结，
  生成 20 条结构化资讯（技术 / 应用 / 行业，侧重技术与应用）
- 输出 Markdown: AI资讯24小时_YYYY年M月D日.md 与 index.html
- 密钥全走环境变量 / Secrets，不硬编码

环境变量：
  ANTHROPIC_API_KEY   必填，LLM 网关 Bearer key（对 agnes 即用其 key）
  ANTHROPIC_BASE_URL  必填，网关基址，如 https://api.agnes-ai.cn/v1
  ANTHROPIC_MODEL     模型名，默认 agnes-2.0-flash
  TAVILY_API_KEY      可选，搜索源；不填则退化为 keyless DuckDuckGo
"""

import os
import re
import datetime
import html as _html
import requests

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BASE_URL = (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.agnes-ai.cn/v1").rstrip("/")
MODEL = os.environ.get("ANTHROPIC_MODEL") or "agnes-2.0-flash"
CHAT_ENDPOINT = BASE_URL + "/chat/completions"

if not API_KEY:
    raise SystemExit("ERROR: 环境变量 ANTHROPIC_API_KEY 未设置")
if not BASE_URL:
    raise SystemExit("ERROR: 环境变量 ANTHROPIC_BASE_URL 未设置")

DATE = datetime.date.today()
DATE_STR = f"{DATE.year}年{DATE.month}月{DATE.day}日"
OUT_MD = f"AI资讯24小时_{DATE_STR}.md"

QUERIES = [
    "AI artificial intelligence news today",
    "OpenAI Anthropic Google DeepMind NVIDIA latest announcement",
    "large language model release August 2026",
    "AI agent coding assistant news",
    "人工智能 大模型 最新动态 今日",
    "字节跳动 阿里 腾讯 百度 大模型 最新发布",
    "AI application industry funding August 2026",
    "AI chip semiconductor news 2026",
    "machine learning research breakthrough this week",
]


def _req_json(url, headers=None, timeout=25):
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print("req_json error:", e)
    return None


def search_tavily(query, max_results=5):
    """优先：Tavily（需 TAVILY_API_KEY，由 workflow 传入；未传入则跳过）。"""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return None
    data = _req_json(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30,
    )
    if not data:
        return None
    out = []
    for it in data.get("results", []):
        out.append({
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "content": (it.get("content") or "")[:600],
            "published": it.get("published_date", ""),
        })
    return out


def search_gnews(query, max_results=5):
    """免 key 兜底：Google News RSS（覆盖中英文全球新闻）。"""
    try:
        from urllib.parse import quote
        url = ("https://news.google.com/rss/search?q=%s&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
               % quote(query))
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        if r.status_code != 200:
            return []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            if link and title:
                out.append({"title": title, "url": link, "content": title, "published": pub})
            if len(out) >= max_results:
                break
        return out
    except Exception as e:
        print("GNews error:", e)
        return []


def search_hn(query, max_results=5):
    """免 key 兜底：Hacker News Algolia（技术深度好）。"""
    from urllib.parse import quote
    data = _req_json(
        "https://hn.algolia.com/api/v1/search?query=%s&tags=story&hitsPerPage=%d"
        % (quote(query), max_results),
        headers={"User-Agent": "Mozilla/5.0"},
    )
    if not data:
        return []
    out = []
    for h in data.get("hits", []):
        oid = h.get("objectID", "")
        url = h.get("url") or ("https://news.ycombinator.com/item?id=%s" % oid)
        out.append({
            "title": h.get("title", ""),
            "url": url,
            "content": (h.get("story_text") or "")[:400] or h.get("title", ""),
            "published": h.get("created_at", ""),
        })
    return out


def search_ddg(query, max_results=5):
    try:
        r = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=25,
        )
        if r.status_code != 200:
            return []
        text = r.text
        titles = re.findall(r'class="result-link"[^>]*>(.*?)</a>', text, re.S)
        urls = re.findall(r'class="result-link"[^>]*href="(.*?)"', text)
        snippets = re.findall(r'class="result-snippet">(.*?)</td>', text, re.S)
        results = []
        for i in range(min(max_results, len(titles))):
            url = urls[i] if i < len(urls) else ""
            title = re.sub(r"<.*?>", "", titles[i]).strip()
            snippet = re.sub(r"<.*?>", "", snippets[i]).strip() if i < len(snippets) else ""
            if url and url.startswith("http"):
                results.append({"title": title, "url": url, "content": snippet, "published": ""})
        return results
    except Exception as e:
        print("DDG error:", e)
        return []


def gather():
    all_res = []
    seen = set()
    for q in QUERIES:
        # Tavily(有 key) -> Google News + HN(免 key) -> DDG(最后兜底)
        res = search_tavily(q) or (search_gnews(q) + search_hn(q)) or search_ddg(q)
        n = 0
        for it in (res or []):
            if it.get("url") and it["url"] not in seen:
                seen.add(it["url"])
                all_res.append(it)
                n += 1
        print(f"query={q!r} -> {n} new results")
    return all_res


def build_context(results):
    lines = []
    for i, it in enumerate(results, 1):
        lines.append(
            f"[{i}] 标题：{it.get('title', '')}\n"
            f"链接：{it.get('url', '')}\n"
            f"摘要：{it.get('content', '')}\n"
        )
    return "\n".join(lines)


PROMPT = """你是资深 AI 资讯编辑。下面是我检索到的「过去 24 小时」全球 AI 动态素材（含来源链接）。
请筛选 20 条最有价值的国内外信息（覆盖 AI 技术、AI 应用、AI 行业动态，侧重技术与应用），避免重复与低质软文。
每条必须包含：标题、摘要、发布日期、来源、原文链接。
按「一、AI 技术 / 二、AI 应用 / 三、AI 行业动态」三栏组织（合计 20 条）。
直接输出 Markdown 正文（从一级标题开始），不要额外解释或前言。

素材：
__CONTEXT__

输出示例结构：
# AI 资讯 24 小时 | __DATE__
## 一、AI 技术
### 1. 标题
- 摘要：……
- 发布日期：2026-08-13
- 来源：OpenAI
- 原文链接：https://……
（其余条目同）
## 二、AI 应用
……
## 三、AI 行业动态
……
"""


def call_llm(messages):
    resp = requests.post(
        CHAT_ENDPOINT,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "max_tokens": 8000, "messages": messages, "temperature": 0.3},
        timeout=300,
    )
    if resp.status_code != 200:
        raise SystemExit(f"ERROR: LLM 调用失败 {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def md_to_html(md, date_str):
    out, in_list = [], False

    def inline(t):
        t = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank">\1</a>', t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        return t

    for line in md.split("\n"):
        s = line.strip()
        if s.startswith("### "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("# "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h1>{inline(s[2:])}</h1>")
        elif s.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(s[2:])}</li>")
        elif s == "":
            if in_list:
                out.append("</ul>"); in_list = False
            out.append("<br>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<p>{inline(s)}</p>")
    if in_list:
        out.append("</ul>")
    body = "\n".join(out)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 资讯 24 小时 | {date_str}</title>
<style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;max-width:860px;margin:0 auto;padding:24px;line-height:1.7;color:#1f2328}}
h1{{font-size:26px;border-bottom:3px solid #2d6cdf;padding-bottom:8px}}
h2{{font-size:21px;margin-top:28px;color:#2d6cdf}}
h3{{font-size:17px;margin-top:18px}}
ul{{background:#f7f9fc;border-left:4px solid #2d6cdf;padding:10px 22px}}
a{{color:#2d6cdf}}
</style></head><body>{body}</body></html>"""


def main():
    results = gather()
    context = build_context(results)
    user_msg = PROMPT.replace("__DATE__", DATE_STR).replace("__CONTEXT__", context)
    messages = [{"role": "user", "content": user_msg}]
    resp = call_llm(messages)
    text = resp["choices"][0]["message"]["content"]
    if not text.strip():
        raise SystemExit("ERROR: 模型未返回正文，可能网关不支持该模型或请求格式不符")
    if not text.lstrip().startswith("#"):
        text = f"# AI 资讯 24 小时 | {DATE_STR}\n\n" + text
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(md_to_html(text, DATE_STR))
    print(f"OK: 已生成 {OUT_MD} ({len(text)} 字符, 检索到 {len(results)} 条素材)")


if __name__ == "__main__":
    main()
