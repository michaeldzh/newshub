#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 AI 资讯生成器（仓库内自包含版本，OpenAI 兼容网关 + 解耦搜索）

检索策略（解耦，不依赖单一来源）：
  1) 直连 RSS：厂商官网 + 中英文主流科技媒体的直接 RSS（来源多样、链接真实）
  2) 关键词检索补充：Tavily(设 TAVILY_API_KEY 时) -> 免 key 的 Google News RSS + Hacker News -> DDG 兜底
将检索结果交给 LLM（OpenAI Chat Completions 格式）总结，生成 20 条结构化资讯。
输出 Markdown: AI资讯24小时_YYYY年M月D日.md 与 index.html（紧凑排版，正文 200–300 字）。
密钥全走环境变量 / Secrets，不硬编码。

环境变量：
  ANTHROPIC_API_KEY   必填，LLM 网关 Bearer key（对 agnes 即用其 key）
  ANTHROPIC_BASE_URL  必填，网关基址，如 https://api.agnes-ai.cn/v1
  ANTHROPIC_MODEL     模型名，默认 agnes-2.0-flash
  TAVILY_API_KEY      可选，搜索源；不填则退化为免 key 检索
"""

import os
import re
import datetime
import xml.etree.ElementTree as ET
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

# ── 多样化直连 RSS（厂商官网 + 中英文主流科技媒体）──────────────────────
FEEDS = [
    # 国际厂商 / 媒体
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://arstechnica.com/ai/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://www.zdnet.com/topic/artificial-intelligence/rss.xml",
    "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://blog.google/technology/ai/rss/",
    "https://openai.com/blog/rss.xml",
    "https://www.anthropic.com/news/rss.xml",
    "https://blogs.nvidia.com/feed/",
    "https://deepmind.google/blog/rss.xml",
    "https://ai.meta.com/blog/rss.xml",
    "https://blogs.microsoft.com/ai/feed/",
    "https://huggingface.co/blog/feed.xml",
    "https://rss.arxiv.org/rss/cs.AI",
    "https://rss.arxiv.org/rss/cs.CL",
    # 国内媒体
    "https://www.qbitai.com/feed",
    "https://36kr.com/feed",
    "https://www.ithome.com/rss/",
    "https://www.zhidx.com/rss.html",
    "https://www.tmtpost.com/rss.xml",
    "https://www.aibase.com/zh/ai-news/rss",
]

# 关键词检索补充（中文 + 英文，覆盖厂商与细分方向）
QUERIES = [
    "AI artificial intelligence news today",
    "OpenAI Anthropic Google DeepMind NVIDIA latest announcement",
    "large language model release August 2026",
    "AI agent coding assistant news",
    "人工智能 大模型 最新动态 今日",
    "字节跳动 阿里 腾讯 百度 大模型 最新发布",
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


def _local(tag):
    """去掉 XML 命名空间前缀，取本地标签名。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(node, name):
    for c in list(node):
        if _local(c.tag) == name:
            return c
    return None


def fetch_feed(url, max_items=3):
    """通用 RSS/Atom 解析（直连来源，免 key，命名空间安全）。失败静默返回空。"""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        nodes = [e for e in root.iter() if _local(e.tag) in ("item", "entry")]
        out = []
        for node in nodes:
            t = _child(node, "title")
            title = (t.text or "").strip() if t is not None else ""
            le = _child(node, "link")
            link = ((le.get("href") if le is not None else None) or
                    (le.text if le is not None else "") or "").strip()
            pub = ""
            for pn in ("pubDate", "published", "updated", "date"):
                pe = _child(node, pn)
                if pe is not None and (pe.text or "").strip():
                    pub = pe.text.strip()
                    break
            desc = ""
            for dn in ("description", "summary", "content", "encoded"):
                de = _child(node, dn)
                if de is not None and (de.text or "").strip():
                    desc = de.text
                    break
            desc = re.sub(r"<.*?>", " ", desc or "")
            desc = re.sub(r"\s+", " ", desc).strip()[:400]
            if title and link:
                out.append({"title": title, "url": link,
                            "content": desc or title, "published": pub})
            if len(out) >= max_items:
                break
        return out
    except Exception as e:
        print(f"feed error {url[:50]}: {e}")
        return []


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
    # 1) 直连 RSS（多样化来源）
    for url in FEEDS:
        for it in fetch_feed(url):
            if it.get("url") and it["url"] not in seen:
                seen.add(it["url"])
                all_res.append(it)
    print(f"feeds -> {len(all_res)} 条素材")
    # 2) 关键词检索补充
    for q in QUERIES:
        res = search_tavily(q) or (search_gnews(q) + search_hn(q)) or search_ddg(q)
        n = 0
        for it in (res or []):
            if it.get("url") and it["url"] not in seen:
                seen.add(it["url"])
                all_res.append(it)
                n += 1
        print(f"query={q!r} -> {n} new results")
    # 控制上下文体量
    return all_res[:100]


def build_context(results):
    lines = []
    for i, it in enumerate(results, 1):
        lines.append(
            f"[{i}] 标题：{it.get('title', '')}\n"
            f"链接：{it.get('url', '')}\n"
            f"摘要：{it.get('content', '')}\n"
        )
    return "\n".join(lines)


PROMPT = """你是资深 AI 资讯编辑。下面是我从「厂商官网 + 中英文主流科技媒体」直接抓取的「过去 24 小时」全球 AI 动态素材（含真实原文链接）。
请严格筛选并输出【恰好 20 条】最有价值的国内外信息，覆盖：一、AI 技术；二、AI 应用；三、AI 行业动态（侧重技术与应用）。避免重复与低质软文。

【每条格式，务必紧凑】
### 序号. 标题
> 来源：真实媒体/厂商名（如 OpenAI、机器之心、TechCrunch、NVIDIA Blog，严禁写“Google News”） · 发布日期（YYYY-MM-DD，无则写“近日”） · [原文](真实链接)
（引用块之后另起一段）正文：用中文客观陈述该动态的要点、关键数据（型号/参数/金额/人名）与行业影响。正文长度必须 200–300 字（按汉字计数，不含空行），宁可写满也不要少于 200 字；不要空话套话，不要分点罗列。

【硬性要求】
- 总数必须恰好 20 条，编号从 1 到 20 连续，三个分区合计 20，不得多、不得少。
- 按三个二级标题分区（每区条数自定，但合计须为 20）。
- 直接输出 Markdown（从一级标题开始），不要前言、不要额外解释。
- 素材链接若是聚合/跳转页，尽量保留指向原始报道的链接；只有聚合链接也接受。

素材：
__CONTEXT__

输出示例：
# AI 资讯 24 小时 | __DATE__
> 今日 20 条 · 来源覆盖厂商官网与中英文科技媒体

## 一、AI 技术
### 1. 标题
> 来源：OpenAI · 2026-08-13 · [原文](https://...)
正文内容 200–300 字……
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
        elif s.startswith("> "):
            out.append(f"<blockquote>{inline(s[2:].strip())}</blockquote>")
        elif s.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(s[2:])}</li>")
        elif s == "":
            if in_list:
                out.append("</ul>"); in_list = False
            # 紧凑：不额外加 <br>
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
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;max-width:820px;margin:0 auto;padding:16px;line-height:1.6;color:#1f2328;font-size:15px}}
h1{{font-size:23px;margin:0 0 10px;border-bottom:3px solid #2d6cdf;padding-bottom:6px}}
h2{{font-size:18px;margin:20px 0 4px;color:#2d6cdf}}
h3{{font-size:15.5px;margin:14px 0 2px;line-height:1.35}}
blockquote{{margin:2px 0 6px;padding:4px 10px;background:#f4f7fb;border-left:3px solid #9db8e8;color:#5a6472;font-size:13px}}
p{{margin:4px 0 10px}}
a{{color:#2d6cdf;text-decoration:none}}
ul{{background:#f7f9fc;border-left:4px solid #2d6cdf;padding:8px 18px;margin:6px 0}}
li{{margin:3px 0}}
</style></head><body>{body}</body></html>"""


def count_items(md):
    """统计资讯条目数（以 '### ' 开头的行）。"""
    return sum(1 for l in md.split("\n") if l.strip().startswith("### "))


def enforce_count(md, target=20):
    """确定性裁剪到恰好 target 条：跨分区按比例配额、连续重编号。

    模型常会多产出（30+ 条），这里不依赖模型听话，而是解析分区后按比例
    保留各分区前若干条，保证三个分区都在且总数恰为 target。
    """
    lines = md.split("\n")
    preamble = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("## "):
            break
        preamble.append(lines[i])
        i += 1
    sections = []  # [(header_line, [ [item_lines...] ])]
    cur_header = None
    cur_items = []
    cur_item = []
    while i < len(lines):
        s = lines[i]
        if s.lstrip().startswith("## "):
            if cur_header is not None:
                if cur_item:
                    cur_items.append(cur_item)
                sections.append((cur_header, cur_items))
            cur_header = s
            cur_items = []
            cur_item = []
        elif s.lstrip().startswith("### "):
            if cur_item:
                cur_items.append(cur_item)
            cur_item = [s]
        else:
            if cur_item:
                cur_item.append(s)
        i += 1
    if cur_header is not None:
        if cur_item:
            cur_items.append(cur_item)
        sections.append((cur_header, cur_items))

    total = sum(len(items) for _, items in sections)
    if total <= target:
        return md

    counts = [len(items) for _, items in sections]
    quotas = [max(1, round(target * c / total)) for c in counts]
    diff = target - sum(quotas)
    k = len(quotas) - 1
    while diff != 0 and k >= 0:
        if diff > 0 and quotas[k] < counts[k]:
            quotas[k] += 1
            diff -= 1
        elif diff < 0 and quotas[k] > 1:
            quotas[k] -= 1
            diff += 1
        k -= 1

    out = list(preamble)
    num = 0
    for (header, items), q in zip(sections, quotas):
        if q <= 0:
            continue
        out.append(header)
        for it in items[:q]:
            num += 1
            first = re.sub(r"^(###\s*)\d+", lambda m: m.group(1) + str(num), it[0])
            out.append(first)
            out.extend(it[1:])
    return "\n".join(out)


def main():
    results = gather()
    context = build_context(results)
    user_msg = PROMPT.replace("__DATE__", DATE_STR).replace("__CONTEXT__", context)
    messages = [{"role": "user", "content": user_msg}]
    resp = call_llm(messages)
    text = resp["choices"][0]["message"]["content"]
    if not text.strip():
        raise SystemExit("ERROR: 模型未返回正文，可能网关不支持该模型或请求格式不符")
    text = text.strip()
    if not text.lstrip().startswith("#"):
        text = f"# AI 资讯 24 小时 | {DATE_STR}\n\n" + text
    text = enforce_count(text, 20)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(text)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(md_to_html(text, DATE_STR))
    print(f"OK: 已生成 {OUT_MD} ({len(text)} 字符, {count_items(text)} 条, 检索到 {len(results)} 条素材)")


if __name__ == "__main__":
    main()
