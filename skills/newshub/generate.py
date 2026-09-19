#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日 AI 资讯生成器（v2 · 确定性去重版）

与 v1 的关键差异
----------------
v1 的去重是「软」的：把最近 3 份日报的标题/链接塞进提示词，指望模型自觉不重复；
而工作流从未把生成的日报提交回仓库，所以那 3 份永远是 0 份 → 跨日去重完全空转，
导致同一事件隔几天就换个链接重发。

v2 的做法：
  1. **全量历史**：读取报告目录下全部 `AI资讯24小时_*.md`（不再只取最近 3 份），
     汇总链接 / 标题 / 事件指纹（见 dedup.py）。
  2. **确定性闸门**：生成后用 dedup.filter_report 硬性丢弃重复与超限条目，
     不依赖模型是否听话。
  3. **缺口自愈**：被丢弃的位置按分区向模型追加补稿，最多 3 轮；
     始终凑不满或仍有硬错误 → **退出码 1**（宁可当天不发，也不推重复内容）。
  4. 提示词里的"已覆盖集合"只是引导（截取近 N 条），真正的判定在本地代码里。

环境变量
--------
  ANTHROPIC_API_KEY   必填，LLM 网关 Bearer key
  ANTHROPIC_BASE_URL  必填，网关基址（如 https://api.agnes-ai.cn/v1）
  ANTHROPIC_MODEL     模型名，默认 agnes-2.0-flash
  TAVILY_API_KEY      可选，搜索源
  REPORT_DIR          可选，日报所在目录（默认本脚本目录）
  HISTORY_PROMPT_LIMIT 可选，提示词中注入的历史条目上限（默认 240）
  MAX_REPAIR_ROUNDS   可选，补稿轮数上限（默认 3）
"""

import datetime
import os
import re
import sys
import xml.etree.ElementTree as ET

import requests

import dedup

REPORT_DIR = os.environ.get("REPORT_DIR") or os.path.dirname(os.path.abspath(__file__))
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BASE_URL = (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.agnes-ai.cn/v1").rstrip("/")
MODEL = os.environ.get("ANTHROPIC_MODEL") or "agnes-2.0-flash"
CHAT_ENDPOINT = BASE_URL + "/chat/completions"
HISTORY_PROMPT_LIMIT = int(os.environ.get("HISTORY_PROMPT_LIMIT") or 240)
MAX_REPAIR_ROUNDS = int(os.environ.get("MAX_REPAIR_ROUNDS") or 3)
TARGET_TOTAL = 20
TARGET_SECTIONS = [7, 7, 6]
# 发布下限：目标 20 条，但不足也照发；低于此值才判定链路异常、不出稿。
MIN_PUBLISH_TOTAL = int(os.environ.get("MIN_PUBLISH_TOTAL") or 8)
SECTION_ORDINALS = "一二三四"

if not API_KEY:
    raise SystemExit("ERROR: 环境变量 ANTHROPIC_API_KEY 未设置")

DATE = datetime.date.today()
DATE_STR = f"{DATE.year}年{DATE.month}月{DATE.day}日"
OUT_MD = f"AI资讯24小时_{DATE_STR}.md"
OUT_MD_PATH = os.path.join(REPORT_DIR, OUT_MD)

# ── 多样化直连 RSS（厂商官网 + 中英文主流科技媒体）──────────────────────
FEEDS = [
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
    "https://www.qbitai.com/feed",
    "https://36kr.com/feed",
    "https://www.ithome.com/rss/",
    "https://www.zhidx.com/rss.html",
    "https://www.tmtpost.com/rss.xml",
    "https://www.aibase.com/zh/ai-news/rss",
]

QUERIES = [
    "AI artificial intelligence news today",
    "OpenAI Anthropic Google DeepMind NVIDIA latest announcement",
    "large language model release",
    "AI agent coding assistant news",
    "人工智能 大模型 最新动态 今日",
    "字节跳动 阿里 腾讯 百度 大模型 最新发布",
    "AI chip semiconductor news",
    "machine learning research breakthrough this week",
]


# ══════════════════════════════════════════════════════════════════════
# 素材检索
# ══════════════════════════════════════════════════════════════════════
def _req_json(url, headers=None, timeout=25, method="GET", payload=None):
    try:
        if method == "POST":
            r = requests.post(url, headers=headers or {}, json=payload, timeout=timeout)
        else:
            r = requests.get(url, headers=headers or {}, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        print(f"  [warn] {method} {url[:60]} -> HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        print("  [warn] req error:", e)
    return None


def _local(tag):
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
            desc = re.sub(r"\s+", " ", re.sub(r"<.*?>", " ", desc or "")).strip()[:400]
            if title and link:
                out.append({"title": title, "url": link,
                            "content": desc or title, "published": pub})
            if len(out) >= max_items:
                break
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] feed error {url[:50]}: {e}")
        return []


def search_tavily(query, max_results=5):
    """Tavily 检索。

    注意：Tavily 的 /search 只接受 **POST + JSON body**；v1 用 GET 且不带 body，
    因此永远拿不到结果（静默退化到 Google News），这里修正为 POST。
    """
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return None
    data = _req_json(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=30, method="POST",
        payload={"query": query, "max_results": max_results, "search_depth": "basic"},
    )
    if not data:
        return None
    return [{
        "title": it.get("title", ""),
        "url": it.get("url", ""),
        "content": (it.get("content") or "")[:600],
        "published": it.get("published_date", ""),
    } for it in data.get("results", [])]


def search_gnews(query, max_results=5):
    """免 key 兜底：Google News RSS。"""
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
    except Exception as e:  # noqa: BLE001
        print("  [warn] GNews error:", e)
        return []


def search_hn(query, max_results=5):
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
        out.append({
            "title": h.get("title", ""),
            "url": h.get("url") or ("https://news.ycombinator.com/item?id=%s" % oid),
            "content": (h.get("story_text") or "")[:400] or h.get("title", ""),
            "published": h.get("created_at", ""),
        })
    return out


def gather():
    all_res, seen = [], set()
    for url in FEEDS:
        for it in fetch_feed(url):
            if it.get("url") and it["url"] not in seen:
                seen.add(it["url"])
                all_res.append(it)
    print(f"feeds -> {len(all_res)} 条素材")
    for q in QUERIES:
        res = search_tavily(q) or (search_gnews(q) + search_hn(q))
        n = 0
        for it in (res or []):
            if it.get("url") and it["url"] not in seen:
                seen.add(it["url"])
                all_res.append(it)
                n += 1
        print(f"query={q!r} -> {n} new")
    return all_res[:120]


def build_context(results):
    return "\n".join(
        f"[{i}] 标题：{it.get('title', '')}\n链接：{it.get('url', '')}\n"
        f"摘要：{it.get('content', '')}\n"
        for i, it in enumerate(results, 1)
    )


# ══════════════════════════════════════════════════════════════════════
# 提示词
# ══════════════════════════════════════════════════════════════════════
PROMPT = """你是资深 AI 资讯编辑。下面是我从「厂商官网 + 中英文主流科技媒体」直接抓取的「过去 24 小时」全球 AI 动态素材（含真实原文链接）。
请严格筛选并输出【恰好 20 条】最有价值的国内外信息，分三个二级标题分区：
## 一、AI 技术（7 条）
## 二、AI 应用（7 条）
## 三、AI 行业动态（6 条）

【每条格式，务必紧凑】
### 序号. 标题
> 来源：真实媒体/厂商名（如 OpenAI、机器之心、TechCrunch、NVIDIA Blog，严禁写“Google News”） · 发布日期（YYYY-MM-DD） · [原文](真实链接)
（引用块之后另起一段）正文：用中文客观陈述该动态的要点、关键数据与行业影响，200–300 字，不分点罗列。

【硬性要求】
- 总数恰好 20 条，编号 1 到 20 连续，三个分区分别为 7 / 7 / 6 条。
- 直接输出 Markdown（从一级标题开始），不要前言、不要额外解释。
- 发布日期必须落在 __LO__ ~ __HI__ 之间。

【强制去重（跨全部历史 + 本日）】
以下"已覆盖集合"只是近期样例，**判定会覆盖仓库中全部历史日报**。严禁重复收录其中的事件；同一事件即便换了媒体、换了链接也不再收录。
若某事件确有实质性新进展（新版本/新金额/新状态），标题须以 `【进展更新】` 开头，且只保留最新一条。
同一厂商单期最多 2 条。成稿后自查：与已覆盖集合零重复、期内零重复、总数恰为 20。

已覆盖集合（样例）：
__DEDUP__

素材：
__CONTEXT__

输出示例：
# AI 资讯 24 小时 | __DATE__
> 今日 20 条 · 来源覆盖厂商官网与中英文科技媒体

## 一、AI 技术
### 1. 标题
> 来源：OpenAI · __HI__ · [原文](https://...)
正文：……
"""

TOPUP_PROMPT = """这是今天的 AI 资讯日报，因部分条目与其他条目/往期日报重复，已被系统剔除。
请**仅补充缺失的条目**，使三个分区回到 7 / 7 / 6 条。

【禁止重复】以下清单中的事件/链接一律不得再出现（含本期已保留条目、已剔除条目、往期已覆盖条目）：
__BANNED__

【仅补充这些】
__NEED__

【格式】只输出需要补充的条目，并带上所属分区标题，例如：
## 二、AI 应用
### 21. 标题
> 来源：媒体名 · __HI__ · [原文](真实链接)
正文：……

要求：来源与链接必须来自下面的素材；正文 200–300 字；发布日期落在 __LO__ ~ __HI__。

素材：
__CONTEXT__
"""


def call_llm(user_msg, max_tokens=8000):
    resp = requests.post(
        CHAT_ENDPOINT,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": user_msg}],
              "temperature": 0.3},
        timeout=300,
    )
    if resp.status_code != 200:
        raise SystemExit(f"ERROR: LLM 调用失败 {resp.status_code}: {resp.text[:500]}")
    text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
    if not text:
        raise SystemExit("ERROR: 模型未返回正文（网关可能不支持该模型）")
    return text


# ══════════════════════════════════════════════════════════════════════
# 输出
# ══════════════════════════════════════════════════════════════════════
def md_to_html(md, date_str):
    out, in_list = [], False

    def inline(t):
        t = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank">\1</a>', t)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

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
        elif s:
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


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════
def section_index(header):
    """把分区标题映射到 0/1/2（按「一/二/三」序数，容错标题措辞变化）。"""
    for i, ch in enumerate(SECTION_ORDINALS):
        if (header or "").strip().startswith(ch):
            return i
    return None


def deficits_of(sections):
    """各分区相比目标 7/7/6 的缺口。"""
    counts = [0, 0, 0]
    for sec in sections:
        idx = section_index(sec["header"])
        if idx is not None and idx < 3:
            counts[idx] += len(sec["items"])
    return [max(0, TARGET_SECTIONS[i] - counts[i]) for i in range(3)], counts


def merge_fragments(base_md, fragment_md):
    """把补稿片段并入主体：按分区归位、去重、连续重编号。"""
    preamble, base_sections = dedup.parse_report(base_md)
    _, frag_sections = dedup.parse_report(fragment_md)

    buckets = {0: [], 1: [], 2: []}
    for sec in frag_sections:
        idx = section_index(sec["header"])
        if idx is not None and idx < 3:
            buckets[idx].extend(sec["items"])

    new_sections = []
    for sec in base_sections:
        idx = section_index(sec["header"])
        if idx is not None and idx < 3 and buckets[idx]:
            sec = {"header": sec["header"], "items": sec["items"] + buckets[idx]}
            buckets[idx] = []
        new_sections.append(sec)
    # 主体里没有的分区（极少见）按序补建
    for idx, extra in buckets.items():
        if extra:
            name = ["AI 技术", "AI 应用", "AI 行业动态"][idx]
            new_sections.append({"header": f"{SECTION_ORDINALS[idx]}、{name}", "items": extra})

    return dedup.render_report(preamble, new_sections)


def banned_block(history, extra_titles, extra_urls, limit=90):
    """给补稿用的禁用清单：往期近期条目 + 本期全部条目（含已剔除的）。"""
    lines = []
    for t in extra_titles[:limit]:
        lines.append(f"- [本期] {t}")
    for u in extra_urls[:limit]:
        lines.append(f"- [本期链接] {u}")
    recent_titles = [t for t, _ in history.titles[-limit:]]
    for t in recent_titles:
        lines.append(f"- [往期] {t}")
    return "\n".join(lines) or "（无）"


def trim_to_target(text, target, section_caps=None):
    """条目数超量时截去多余条目，返回 (新文本, 截掉条数)。

    先按分区上限（section_caps，如 7/7/6）削平超量分区，再从末尾分区往前截，
    确保「各分区不得超上限」这条硬约束不会因截尾而破。模型偶尔多给几条时，
    截尾比整期不出稿划算。
    """
    preamble, sections = dedup.parse_report(text)
    before = sum(len(s["items"]) for s in sections)
    if section_caps:
        for i, cap in enumerate(section_caps):
            if i < len(sections) and len(sections[i]["items"]) > cap:
                sections[i]["items"] = sections[i]["items"][:cap]
    over = sum(len(s["items"]) for s in sections) - target
    for idx in range(len(sections) - 1, -1, -1):
        if over <= 0:
            break
        take = min(over, len(sections[idx]["items"]))
        if take:
            sections[idx]["items"] = sections[idx]["items"][:-take]
            over -= take
    after = sum(len(s["items"]) for s in sections)
    if after == before:
        return text, 0
    return dedup.render_report(preamble, sections), before - after


def main():
    print("=" * 66)
    print(f"AI 资讯生成 | {DATE_STR} | 报告目录 {REPORT_DIR}")
    print("=" * 66)

    # 1) 全量历史（v1 只取最近 3 份，且因仓库无文件而恒为空）
    history = dedup.load_history(REPORT_DIR, exclude={OUT_MD}, before=DATE)
    print(f"历史基线：{len(history.files)} 期 / {len(history.titles)} 条标题 / "
          f"{len(history.urls)} 条链接 / {len(history.fps)} 条事件指纹")
    if not history.files:
        print("  [warn] 未读到任何历史日报 —— 跨日去重将无基准。"
              "请确认工作流已把历史日报提交回仓库（见 ai-news.yml 的 Commit report 步骤）")

    # 2) 素材
    results = gather()
    context = build_context(results)
    if not results:
        raise SystemExit("ERROR: 未检索到任何素材，终止（避免凭空生成）")

    # 3) 首轮生成
    covered = []
    for t, _ in history.titles[-HISTORY_PROMPT_LIMIT:]:
        covered.append(t)
    for u in list(history.urls)[-HISTORY_PROMPT_LIMIT:]:
        covered.append(u)
    covered_block = "\n".join(f"- {c}" for c in covered) or "（无，本期为首期）"
    lo, hi = DATE - datetime.timedelta(days=1), DATE

    text = call_llm(PROMPT.replace("__DATE__", DATE_STR)
                    .replace("__CONTEXT__", context)
                    .replace("__DEDUP__", covered_block)
                    .replace("__LO__", str(lo)).replace("__HI__", str(hi)))
    if not text.lstrip().startswith("#"):
        text = f"# AI 资讯 24 小时 | {DATE_STR}\n\n" + text

    # 4) 闸门 + 缺口自愈
    dropped_all, final_items, final_sections = [], [], []
    for rnd in range(1, MAX_REPAIR_ROUNDS + 1):
        text, kept, dropped = dedup.filter_report(text, history, DATE)
        if dropped:
            dropped_all.extend(dropped)
        errors, warns, final_items, final_sections = dedup.gate(
            text, history, DATE, expected_total=None, expected_sections=None)
        need, counts = deficits_of(final_sections)
        print(f"[轮次 {rnd}] 保留 {len(final_items)} 条 分布 {counts} | "
              f"本轮剔除 {len(dropped)} 条 | 残留错误 {len(errors)} 条 | 缺口 {need}")
        for it, reason in dropped:
            print(f"    × {reason} ← {it['title'][:38]}")
        for e in errors:
            print(f"    ! {e}")
        if len(final_items) >= TARGET_TOTAL and not errors:
            break
        if rnd == MAX_REPAIR_ROUNDS:
            break
        if sum(need) == 0 and errors:
            # 数量够但有硬错误（如日期超窗）→ 仍走补稿，让模型替换掉问题条目
            need = [0, 0, 0]
        want = [f"{SECTION_ORDINALS[i]}、{['AI 技术','AI 应用','AI 行业动态'][i]} 补 {need[i]} 条"
                for i in range(3) if need[i] > 0]
        if not want:
            print("    → 无可补缺口，结束自愈")
            break
        frag = call_llm(TOPUP_PROMPT
                        .replace("__BANNED__", banned_block(
                            history,
                            [i["title"] for i in final_items] + [i["title"] for i, _ in dropped_all],
                            [i["url"] for i in final_items if i["url"]]))
                        .replace("__NEED__", "\n".join(f"- {w}" for w in want))
                        .replace("__CONTEXT__", context)
                        .replace("__LO__", str(lo)).replace("__HI__", str(hi)))
        text = merge_fragments(text, frag)

    # 5) 终检：目标 20 条，不足也照发；仅低于下限或存在硬错误才不出稿
    #    超出目标先截尾（保持各分区不超上限），避免模型多给两条就整天不发
    text, trimmed = trim_to_target(text, TARGET_TOTAL, TARGET_SECTIONS)
    if trimmed:
        print(f"  [info] 超出目标，已截尾 {trimmed} 条至 {TARGET_TOTAL} 条")

    errors, warns, final_items, final_sections = dedup.gate(
        text, history, DATE, expected_total=TARGET_TOTAL,
        expected_sections=TARGET_SECTIONS, min_total=MIN_PUBLISH_TOTAL)
    counts = [len(sec["items"]) for sec in final_sections]
    print(f"终检：{len(final_items)} 条 | 分布 {counts} | 错误 {len(errors)} | 告警 {len(warns)}")
    if len(final_items) < MIN_PUBLISH_TOTAL:
        for path in (OUT_MD_PATH, os.path.join(REPORT_DIR, "index.html")):
            if os.path.exists(path):
                os.remove(path)
        raise SystemExit(f"FAIL: 去重后仅 {len(final_items)} 条，低于发布下限 "
                         f"{MIN_PUBLISH_TOTAL}，本轮不产出（请排查素材源与模型输出）")
    if len(final_items) < TARGET_TOTAL:
        print(f"  [WARN] 仅 {len(final_items)} 条（目标 {TARGET_TOTAL}）—— "
              f"按「不足也照发」策略放行，本期缺口条目之后可正常复用")
    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")
        raise SystemExit("FAIL: 仍存在硬性问题，本轮不产出、不推送")
    for w in warns:
        print(f"  [WARN] {w}")

    with open(OUT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    with open(os.path.join(REPORT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(md_to_html(text, DATE_STR))

    print(f"OK: 已生成 {OUT_MD}（{len(final_items)} 条，分布 {counts}，"
          f"剔除重复 {len(dropped_all)} 条，素材 {len(results)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
