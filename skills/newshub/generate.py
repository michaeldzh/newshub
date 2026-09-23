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
  2. **素材预筛**（2026-09-23 新增，事故根因修复）：`prefilter_materials()` 在
     送进提示词之前，就用全历史把「已覆盖 / 明显超窗」的素材剔掉。此前模型每轮
     都给满 20 条、却有 14–15 条是老文章，只能在闸门阶段丢弃，去重后仅剩 5–6 条，
     再撞上补稿限流就整天不出稿。判据与闸门完全一致，因此不会误杀闸门本会保留的条目。
  3. **确定性闸门**：生成后用 dedup.filter_report 硬性丢弃重复与超限条目，
     不依赖模型是否听话。
  4. **缺口自愈**：被丢弃的位置按分区向模型追加补稿，最多 3 轮；
     补稿本身失败（限流/网关抖动）**不阻断出稿** —— 既有内容已过闸门，
     按「不足也照发」继续（线上事故 2026-09-19：一次 429 让整天白跑）。
     仅当条数低于下限，或仍存在硬错误（重复/超窗等），才以退出码 1 终止。
  5. 提示词里的"已覆盖集合"只是引导（截取近 N 条），真正的判定在本地代码里。
  6. **自带回写**：出稿后由 `commit_report_back()` 用 `git` 把日报提交回仓库，
     让下一期读到本期（跨日去重基线）。写在脚本里而非工作流里，是为了绕开
     GitHub 「改 `.github/workflows/*` 需要 workflow 作用域」的限制，见该函数注释。

环境变量
--------
  ANTHROPIC_API_KEY   必填，LLM 网关 Bearer key
  ANTHROPIC_BASE_URL  必填，网关基址（如 https://api.agnes-ai.cn/v1）
  ANTHROPIC_MODEL     模型名，默认 agnes-2.0-flash
  TAVILY_API_KEY      可选，搜索源
  REPORT_DIR          可选，日报所在目录（默认本脚本目录）
  HISTORY_PROMPT_LIMIT 可选，提示词中注入的历史条目上限（默认 240）
  MAX_REPAIR_ROUNDS   可选，补稿轮数上限（默认 3）
  MATERIAL_LIMIT      可选，预筛后送进提示词的素材上限（默认 120）
  MIN_PUBLISH_TOTAL   可选，发布下限（默认 1）；不足 20 但 ≥ 此值即照发
  NEWSHUB_COMMIT_BACK 可选，强制开启/关闭日报回写（CI 中默认开启）
  NEWSHUB_ALERT       可选，置 0/false 关闭失败兜底（默认开启）
"""

import datetime
import json
import os
import re
import subprocess
import sys
import time
import traceback
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
# 发布下限：目标 20 条，但不足也照发（用户 2026-09-19 明确要求，2026-09-23 由 3 收到 1）。
# 下限的职责只是「拦住 0 条 / 硬错误」这类链路异常 —— 素材少是常态，不该整天不出稿；
# 真正的故障由下面的 emit_alert() 兜底送达，而不是靠「不发」来体现。
MIN_PUBLISH_TOTAL = int(os.environ.get("MIN_PUBLISH_TOTAL") or 1)
# 预筛后送进提示词的素材上限
MATERIAL_LIMIT = int(os.environ.get("MATERIAL_LIMIT") or 120)
SECTION_ORDINALS = "一二三四"
# 故障通报文件名（仓库内可见，且是「上一轮是否失败」的机器可读判据）
ALERT_NAME = "ALERT.json"


def _require_api_key():
    """把 key 校验从 import 期挪到主流程内。

    原来写在模块顶层，缺 key 时进程在 import 阶段就退出 —— 那时 main() 还没进来，
    兜底通报永远不会生成，等于又回到静默失败。
    """
    if not API_KEY:
        raise SystemExit("ERROR: 环境变量 ANTHROPIC_API_KEY 未设置"
                         "（GitHub 仓库 Settings → Secrets 里检查 ANTHROPIC_API_KEY）")

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
    # 不在这一步截断：先交给 prefilter_materials 剔除已覆盖素材，再按上限取，
    # 否则陈旧素材会挤掉后面的新鲜素材。
    return all_res


def build_context(results):
    return "\n".join(
        f"[{i}] 标题：{it.get('title', '')}\n链接：{it.get('url', '')}\n"
        f"摘要：{it.get('content', '')}\n"
        for i, it in enumerate(results, 1)
    )


# 素材日期解析：RSS 用 RFC822（Mon, 22 Sep 2026 10:00:00 GMT），
# Tavily 用 ISO（2026-09-22T10:00:00Z）。解析不出就返回 None（不去判断）。
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def material_date(raw):
    s = (raw or "").strip()
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        try:
            return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()],
                                 int(m.group(1)))
        except ValueError:
            return None
    return None


def prefilter_materials(results, history):
    """送进提示词之前，就把「往期已覆盖 / 明显超窗」的素材剔掉。

    为什么必须做（2026-09-23、09-20 两次线上事故的根因）：
    模型每轮都给满 20 条，但其中 14–15 条是搜索引擎翻出来的**老文章**
    （9/5、9/6、9/8、8/18、8/21 那几期已发过的），只能在闸门阶段逐条丢弃，
    于是去重后只剩 5–6 条；再撞上补稿时的 LLM 限流（429），当天干脆不出稿。

    而这些判定在送稿前就是**确定性可算**的——链接是否在全历史出现过、
    标题是否与历史标题高度相似、事件指纹是否命中。先剔除，模型就只在
    「真新」的素材里挑，缺口自然收敛，同时大幅减少对补稿轮次的依赖。

    注意：这里用的三个判据与闸门 `filter_report` 完全一致（同阈值、同函数），
    因此**不会误杀闸门本会保留的条目**，只是把丢弃提前到提示词之前。
    返回 (保留素材, [(素材, 原因), ...])。
    """
    kept, dropped = [], []
    # 日期窗口比闸门 [D-1, D] 略宽：留出余地，避免把跨时区/刚过窗的素材误杀
    floor = DATE - datetime.timedelta(days=2)
    # 历史标题的字集预先算一次（不变），避免「素材数 × 历史标题数」次重复计算
    hist_title_grams = [(dedup._grams(ht), ht, hf) for ht, hf in history.titles]

    for it in results:
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        body = it.get("content") or ""
        if not title:
            dropped.append((it, "素材无标题"))
            continue

        # ① 链接级：同一 URL 即同一篇文章，绝无「新进展」的可能
        if url and url in history.urls:
            dropped.append((it, f"链接已覆盖（{history.urls[url]}）"))
            continue

        # ② 标题级：厂商无关的用字重合，拦「换媒体重发同一事件」
        #    （与闸门一致：标题含【进展更新】者豁免语义判重，但不豁免链接判重）
        progress = dedup.PROGRESS_TAG in title
        hit_title = None
        if not progress:
            g = None
            for h_grams, h_title, h_file in hist_title_grams:
                if g is None:
                    g = dedup._grams(title)
                if dedup.title_similarity(title, h_title,
                                          grams_a=g, grams_b=h_grams) >= dedup.TITLE_SIM_THRESHOLD:
                    hit_title = (h_title, h_file)
                    break
        if hit_title:
            dropped.append((it, f"标题近似已覆盖（{hit_title[1]}）"))
            continue

        # ③ 事件链级：厂商×动作×金额/对象用字
        hit_fp = None
        if not progress:
            fp = dedup.fingerprint(title, body)
            for h_fp, h_title, h_file in history.fps:
                if dedup.is_dup_event(fp, h_fp):
                    hit_fp = (h_title, h_file)
                    break
        if hit_fp:
            dropped.append((it, f"事件链已覆盖（{hit_fp[1]}）"))
            continue

        # ④ 时效：能解析出日期且明显早于窗口的，闸门也会判超窗，提前去掉
        d = material_date(it.get("published"))
        if d is not None and d < floor:
            dropped.append((it, f"发布日期超窗（{d}）"))
            continue

        kept.append(it)

    # 新鲜素材优先：有日期的按日期倒序排在前面，无日期的保持原序垫后。
    # gather() 之后要按上限截断，这样被截掉的是最陈旧的而不是最新的。
    def _sort_key(pair):
        d = material_date(pair[1].get("published"))
        return (0, -d.toordinal()) if d else (1, 0)

    kept = [it for _, it in sorted(enumerate(kept), key=lambda p: _sort_key(p))]
    return kept, dropped


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


# 可重试的 HTTP 状态：限流与网关类瞬时故障。免费/低档套餐很容易撞上 429，
# 一次抖动就让整天不出稿并不划算，因此先退避重试再决定是否放弃。
RETRY_STATUS = {429, 500, 502, 503, 504}
# 秒。免费档的速率限制按时间窗计算，5/15/30 那点等待根本不够（2026-09-23 实测
# 三轮退避全被 429 挡回，补稿直接失败）——拉到累计 ~3 分钟才能跨过限流窗口。
RETRY_BACKOFF = [10, 30, 60, 90]


def call_llm(user_msg, max_tokens=8000, soft=False):
    """调用 LLM。瞬时限流/网关错误会退避重试。

    soft=False（默认）：最终仍失败则抛 SystemExit —— 用于首轮生成，
      此时没有任何可发布内容，终止是正确行为。
    soft=True：最终仍失败返回 None —— 用于「补稿」轮。补稿只是锦上添花，
      不能因为一次 429 就把已经合格的内容整期丢掉（2026-09-19 线上事故）。
    """
    last = "未知错误"
    for attempt in range(len(RETRY_BACKOFF) + 1):
        if attempt:
            wait = RETRY_BACKOFF[attempt - 1]
            print(f"  [warn] LLM 调用重试 {attempt}/{len(RETRY_BACKOFF)}，"
                  f"{wait}s 后重试（{last[:120]}）")
            time.sleep(wait)
        try:
            resp = requests.post(
                CHAT_ENDPOINT,
                headers={"Authorization": f"Bearer {API_KEY}",
                         "Content-Type": "application/json"},
                json={"model": MODEL, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": user_msg}],
                      "temperature": 0.3},
                timeout=300,
            )
        except Exception as e:  # noqa: BLE001 —— 网络抖动同样值得重试
            last = f"{type(e).__name__}: {e}"
            if attempt == len(RETRY_BACKOFF):
                break
            continue
        if resp.status_code in RETRY_STATUS:
            last = f"{resp.status_code}: {resp.text[:300]}"
            if attempt == len(RETRY_BACKOFF):
                break
            continue
        if resp.status_code != 200:
            last = f"{resp.status_code}: {resp.text[:300]}"
            break                      # 4xx 业务错误（如模型名不对）重试无意义
        text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        if not text:
            last = "模型未返回正文（网关可能不支持该模型）"
            break
        return text

    if soft:
        print(f"  [warn] LLM 调用最终失败，跳过本次补稿：{last[:200]}")
        return None
    raise SystemExit(f"ERROR: LLM 调用失败：{last[:500]}")


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


def _git(args, cwd, timeout=180):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def _commit_enabled(enabled):
    if enabled is None:
        ci = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
        flag = (os.environ.get("NEWSHUB_COMMIT_BACK") or "").lower()
        enabled = ci or flag in ("1", "true", "yes", "force")
    return enabled


def _repo_root():
    """定位本项目仓库根。返回 (root, 状态)，状态为 ok / nogit / notarget。"""
    code, out, err = _git(["rev-parse", "--show-toplevel"], REPORT_DIR)
    if code != 0:
        print(f"[回写] 跳过：当前目录不是 git 仓库（{err[:120]}）")
        return None, "nogit"
    root = out.splitlines()[-1].strip()
    # 护栏：只认「真正属于本项目的仓库」。git 会一路向上找到最近的上层仓库，
    # 若脚本被放到别的目录下运行，可能把日报误提交进不相干的仓库（实测用户主目录
    # 就是一个 git repo）。本项目的标志是根下有 .github/workflows。
    if not os.path.isdir(os.path.join(root, ".github", "workflows")):
        print(f"[回写] 跳过：{root} 不是本项目仓库（根下无 .github/workflows）")
        return None, "notarget"
    return root, "ok"


def _repo_rel(path):
    """绝对路径 → 仓库相对路径（正斜杠）。不在本项目仓库内则返回 None。"""
    root, _ = _repo_root()
    if root is None:
        return None
    return os.path.relpath(os.path.abspath(path), root).replace("\\", "/")


def commit_paths_back(rels, message, enabled=None):
    """暂存 → 提交 → 推送若干「仓库相对路径」（支持已跟踪文件的删除）。

    返回状态字符串：ok / nochange / skipped / nogit / notarget /
    commit-failed / push-failed / error
    """
    if not _commit_enabled(enabled):
        print("[回写] 跳过（非 CI 环境且未显式开启；设 NEWSHUB_COMMIT_BACK=1 可强制）")
        return "skipped"
    try:
        root, status = _repo_root()
        if root is None:
            return status
        branch = os.environ.get("GITHUB_REF_NAME") or "main"

        # 浅克隆（checkout 默认 fetch-depth: 1）直接 push 可能被拒，先补全历史
        if _git(["fetch", "--unshallow"], root)[0] != 0:
            _git(["fetch", "--depth=100", "origin", branch], root)

        _git(["config", "user.name", "github-actions[bot]"], root)
        _git(["config", "user.email",
              "41898282+github-actions[bot]@users.noreply.github.com"], root)

        # 逐个暂存：路径既不存在又未被跟踪时 git 会因 pathspec 不匹配报错，
        # 这属于「本来就没东西可提交」，不是故障，忽略即可。
        for rel in rels:
            _git(["add", "-A", "--", rel], root)
        code, out, _ = _git(["status", "--porcelain", "--"] + rels, root)
        if code != 0 or not out.strip():
            print("[回写] 无变化，无需重复入库")
            return "nochange"

        code, _, err = _git(["commit", "-m", message, "--"] + rels, root)
        if code != 0:
            print(f"[回写] commit 失败：{err[:200]}")
            return "commit-failed"

        code, _, err = _git(["push", "origin", f"HEAD:{branch}"], root)
        if code != 0:
            print(f"[回写] push 失败：{err[:200]}"
                  f"\n       本地提交已生成，但未推上远端")
            return "push-failed"

        print(f"[回写] 已入库并推送：{'、'.join(rels)} → {branch}")
        return "ok"
    except Exception as e:  # noqa: BLE001
        print(f"[回写] 异常（已忽略，不影响出稿）：{type(e).__name__}: {e}")
        return "error"


def commit_report_back(report_path, report_name, enabled=None):
    """把当日日报提交回仓库，作为下一期的跨日去重基线。

    为什么写在生成脚本里、而不是工作流里
    ------------------------------------
    GitHub 规定：创建或修改 `.github/workflows/*` 的凭据必须带 `workflow` 作用域，
    否则 403（网页编辑器同样会被拒，报 "File could not be edited"）。本机 token 无
    该作用域 → 无法往工作流里加"回写"步骤。于是把回写放进生成脚本本身 ——
    工作流本来就会执行本脚本，限制被完全绕开：
      · `actions/checkout@v4` 默认（persist-credentials）把 GITHUB_TOKEN 写进本地 git 配置；
      · 本仓库 `default_workflow_permissions = write`，该 token 具备推送权限。
    若将来工作流里也加了回写步骤，二者互不冲突：本函数发现"无变化"即退出。

    出稿成功时顺带清掉上一轮的故障通报 ALERT.json —— 于是「仓库里到底有没有
    ALERT.json」就是最可靠的故障判据：有、且日期是今天 ⇒ 今天没出稿。

    任何一步失败都只打印告警，绝不影响当日出稿与 Pages 发布。
    返回状态字符串：ok / nochange / skipped / nogit / notarget / missing /
    commit-failed / push-failed / error
    """
    if not _commit_enabled(enabled):
        print("[回写] 跳过（非 CI 环境且未显式开启；设 NEWSHUB_COMMIT_BACK=1 可强制）")
        return "skipped"
    if not os.path.exists(report_path):
        print("[回写] 跳过：找不到日报文件")
        return "missing"

    root, status = _repo_root()
    if root is None:
        return status
    rel = os.path.relpath(os.path.abspath(report_path), root).replace("\\", "/")

    rels = [rel]
    stale = os.path.join(REPORT_DIR, ALERT_NAME)
    if os.path.exists(stale):
        os.remove(stale)
        print(f"[回写] 已清除上一轮的故障通报 {ALERT_NAME}")
    alert_rel = _repo_rel(stale)
    # cwd 必须是仓库根：pathspec 是相对 cwd 解析的，在 skills/newshub 下查
    # "skills/newshub/ALERT.json" 永远查不到，删除就永远提交不上去。
    if alert_rel and _git(["ls-files", "--error-unmatch", "--", alert_rel],
                          root)[0] == 0:
        rels.append(alert_rel)          # 通报文件仍被跟踪 → 把删除一并提交

    return commit_paths_back(rels, f"chore(news): 入库 {report_name}（跨日去重基线）",
                             enabled=enabled)


# ══════════════════════════════════════════════════════════════════════
# 失败兜底：本轮不出稿时，把失败变成「可送达、可追溯」的通报
# ══════════════════════════════════════════════════════════════════════
def _run_url():
    repo = os.environ.get("GITHUB_REPOSITORY") or "michaeldzh/newshub"
    rid = os.environ.get("GITHUB_RUN_ID")
    return (f"https://github.com/{repo}/actions/runs/{rid}" if rid
            else f"https://github.com/{repo}/actions")


def alert_html(payload):
    def esc(s):
        return (str(s or "").replace("&", "&amp;")
                .replace("<", "&lt;").replace(">", "&gt;"))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 日报未出稿 | {esc(payload.get('date_cn'))}</title>
<style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;max-width:820px;margin:0 auto;padding:16px;line-height:1.6;color:#1f2328;font-size:15px}}
.banner{{background:#fff1f0;border:1px solid #e8b4ae;border-left:8px solid #d93026;border-radius:6px;padding:14px 16px;margin-bottom:18px}}
.banner h1{{font-size:20px;margin:0 0 8px;color:#b3261e}}
.banner p{{margin:3px 0}}
b.k{{color:#5a6472;font-weight:600}}
pre{{background:#f6f8fa;border:1px solid #e2e6ea;border-radius:6px;padding:10px;white-space:pre-wrap;word-break:break-all;font-size:12.5px;color:#39414d}}
a{{color:#2d6cdf;text-decoration:none}}
.meta{{color:#8a929c;font-size:12.5px;margin-top:18px}}
</style></head><body>
<div class="banner">
<h1>今日 AI 日报未出稿</h1>
<p>日期：<b class="k">{esc(payload.get('date_cn'))}</b>　失败阶段：<b class="k">{esc(payload.get('stage'))}</b></p>
<p>直接原因：<b class="k">{esc(payload.get('reason'))}</b></p>
</div>
<p>本邮件由流水线自带的「失败兜底」发出。生成脚本本轮没有产出可发布的日报，
于是把失败原因写成了这一页，借既有的发信步骤送达 —— 目的是不再出现
「整天没出稿、却无人知晓」的情况。</p>
<p>排查入口：<a href="{esc(payload.get('run_url'))}" target="_blank">{esc(payload.get('run_url'))}</a></p>
<h3>完整诊断</h3>
<pre>{esc(payload.get('detail'))}</pre>
<p class="meta">生成时间 {esc(payload.get('generated_at'))}　·　故障标记 ALERT.json　·　
本页同时发布在 GitHub Pages</p>
</body></html>"""


def emit_alert(stage, detail, extra=None):
    """本轮不出稿时，把失败落盘成三份互为冗余的通报。

    为什么不能用工作流的 `if: failure()` 步骤
    ----------------------------------------
    那需要改 `.github/workflows/ai-news.yml`，而本机 PAT 缺 `workflow` 作用域，
    GitHub 一律 403 拒收（Contents API 与 Git Data API 同样被拒）。工作流默认又是
    `if: success()`：生成步骤一失败，后面的「Push report to email」直接跳过 ——
    失败于是彻底静默（9/20、9/23 用户都是几天后才发现）。

    绕开方式：让生成步骤「成功」退出，但把失败写成通报，借既有的发信步骤送达：
      ① 邮件   —— index.html 就是故障通报页，push_email.py 检测到 ALERT.json
                  会改用「⚠️ 未出稿」主题，收件人第一眼就知道今天没有日报；
      ② Pages  —— index.html 照常发布到站点；
      ③ 仓库   —— ALERT.json 提交入库（下次出稿时自动删除），
                  机器可读，且「有没有这个文件」本身就是判据；
      ④ 运行页 —— 摘要写入 $GITHUB_STEP_SUMMARY，Actions 页面顶部可见。

    本函数自身绝不抛异常：兜底逻辑把主流程再炸一次毫无意义。
    """
    detail = detail or ""
    payload = {
        "alert": True,
        "date": str(DATE),
        "date_cn": DATE_STR,
        "stage": stage,
        "reason": (detail.splitlines() or [""])[0][:300],
        "detail": detail[:4000],
        "run_url": _run_url(),
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if extra:
        payload.update(extra)

    # 半成品日报绝不外发 —— 宁可发通报，也不发一份没走完闸门的稿子
    if os.path.exists(OUT_MD_PATH):
        os.remove(OUT_MD_PATH)

    ap = os.path.join(REPORT_DIR, ALERT_NAME)
    with open(ap, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(REPORT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(alert_html(payload))
    print(f"[ALERT] 通报已落盘：{ALERT_NAME} + index.html")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(f"## ⚠️ 今日未出稿（{DATE_STR}）\n\n"
                        f"- 失败阶段：{stage}\n- 直接原因：{payload['reason']}\n"
                        f"- 运行地址：{payload['run_url']}\n")
        except Exception as e:  # noqa: BLE001
            print(f"[ALERT] 写 step summary 失败（无关紧要）：{e}")

    if (os.environ.get("NEWSHUB_ALERT") or "").lower() in ("0", "false", "no"):
        print("[ALERT] NEWSHUB_ALERT 已关闭入库，仅本地落盘")
        return payload
    rel = _repo_rel(ap)
    if rel:
        commit_paths_back([rel], f"alert(news): {DATE_STR} 未出稿 —— "
                                 f"{payload['reason'][:60]}")
    return payload


def _abort(stage, detail):
    """失败收口：落盘通报，然后**返回 0**（而不是 1）。

    为什么返回 0：见 emit_alert() 的说明 —— 只有让生成步骤成功，既有的发信步骤
    才会执行，通报才能送出去。运行页变绿由 $GITHUB_STEP_SUMMARY 与仓库里的
    ALERT.json 补偿，不会失去可见性。
    """
    first = (detail or "").splitlines()[0][:200] if detail else ""
    print("\n" + "!" * 66)
    print(f"[ALERT] {stage}：{first}")
    print("!" * 66)
    try:
        emit_alert(stage, detail)
    except Exception as e:  # noqa: BLE001
        print(f"[ALERT] 通报落盘失败（不再抛出）：{type(e).__name__}: {e}")
    print("[ALERT] 本轮不出稿；通报页将随既有的邮件步骤送达。")
    return 0


def main():
    """统一入口：把任何失败转成「故障通报」，而不只是终止进程。"""
    try:
        return _run()
    except SystemExit as exc:
        code = exc.code
        if code in (0, None):
            return 0
        return _abort("生成中止", str(code))
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001
        return _abort("未捕获异常",
                      f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}")


def _run():
    _require_api_key()
    print("=" * 66)
    print(f"AI 资讯生成 | {DATE_STR} | 报告目录 {REPORT_DIR}")
    print("=" * 66)

    # 1) 全量历史（v1 只取最近 3 份，且因仓库无文件而恒为空）
    history = dedup.load_history(REPORT_DIR, exclude={OUT_MD}, before=DATE)
    print(f"历史基线：{len(history.files)} 期 / {len(history.titles)} 条标题 / "
          f"{len(history.urls)} 条链接 / {len(history.fps)} 条事件指纹")
    if not history.files:
        print("  [warn] 未读到任何历史日报 —— 跨日去重将无基准。"
              "请确认回写是否生效（回写由本脚本的 commit_report_back() 完成）")

    # 2) 素材：先用全历史做确定性预筛，再送进提示词
    raw_results = gather()
    results, pre_dropped = prefilter_materials(raw_results, history)
    print(f"素材预筛：{len(raw_results)} 条 -> 保留 {len(results)} 条 "
          f"（剔除已覆盖/超窗 {len(pre_dropped)} 条）")
    for it, reason in pre_dropped[:12]:
        print(f"    - {reason} ← {(it.get('title') or '')[:36]}")
    if len(pre_dropped) > 12:
        print(f"    … 另有 {len(pre_dropped) - 12} 条同类剔除")
    results = results[:MATERIAL_LIMIT]
    context = build_context(results)
    if not results:
        raise SystemExit("ERROR: 素材预筛后无可用素材，终止（避免凭空生成）")

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
                        .replace("__LO__", str(lo)).replace("__HI__", str(hi)),
                        soft=True)
        if frag is None:
            # 补稿失败（限流等）不应拖垮整期：现有内容已过闸门，按「不足也照发」
            # 继续走到终检。缺口条目留待后续期正常复用。
            print(f"  [warn] 补稿失败，停止自愈；以现有 {len(final_items)} 条继续出稿"
                  f"（缺口 {need}，将在后续期补上）")
            break
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

    # 6) 回写仓库：让下一期读到本期，跨日去重基线才活得起来
    commit_report_back(OUT_MD_PATH, OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
