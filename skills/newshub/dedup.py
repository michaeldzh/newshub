#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去重核心模块（格式感知 + 确定性判定）。

背景与职责
----------
原实现把去重完全寄托在「提示词里请模型不要重复」+「读最近 3 份日报」上，
而仓库里从未有过日报文件，导致「已覆盖集合」恒为空、跨日去重彻底空转。
本模块提供**确定性**判定与过滤，不依赖模型是否听话：

  parse_report()   解析日报正文（适配本仓库真实格式）
  load_history()   汇总全部历史日报的「链接 / 标题 / 事件指纹」
  gate()           逐项校验，返回 errors / warnings
  filter_report()  按规则丢弃违规条目并连续重编号（生成阶段自愈用）

日报真实格式（由 generate.py 的 PROMPT 产出）::

    # AI 资讯 24 小时 | 2026年9月18日
    > 今日 20 条 · 来源覆盖厂商官网与中英文科技媒体

    ## 一、AI 技术
    ### 1. 标题
    > 来源：IT之家 · 2026-09-18 · [原文](https://...)
    正文：……

同时兼容旧格式（**摘要** / **原文链接**：…），以便把历史日报直接吃进来做比对。

判定规则
--------
E2  本期内部链接不得重复
E3  链接不得与全部历史重复（标【进展更新】降级为 WARN）
E4  发布日期须在 [D-1, D]（无日期或“近日”按 WARN 处理）
E5  每条须有标题 / 链接 / 来源 / 正文
E7  事件链指纹去重：期内 + 全部历史（厂商×动作×金额 / 标题 2-gram≥0.45）
E8  单期同一厂商 ≤2 条
E9  标题相似度去重：与任一条历史标题 2-gram Jaccard ≥0.65 即判重（**厂商无关**）
"""

import datetime
import glob
import os
import re

# ── 厂商词表（仅用于去重判定；标题中出现的厂商才计入）────────────────────
VENDORS = [
    "OpenAI", "Anthropic", "Google", "DeepMind", "谷歌", "微软", "Microsoft",
    "阿里", "阿里巴巴", "阿里云", "腾讯", "字节", "字节跳动", "小米", "华为",
    "NVIDIA", "英伟达", "Meta", "DeepSeek", "深度求索", "智谱", "月之暗面",
    "Mistral", "Cohere", "Arm", "苹果", "Apple", "百度", "讯飞", "科大讯飞",
    "面壁", "Cognition", "xAI", "亚马逊", "AWS", "三星", "特斯拉", "京东",
    "美团", "网易", "快手", "商汤", "寒武纪", "燧原", "摩尔线程", "壁仞",
    "昆仑芯", "智象", "蚂蚁", "钉钉", "微信", "天猫", "淘宝", "金山", "WPS",
    "Siri", "Copilot", "ChatGPT", "Claude", "Gemini", "Llama", "Qwen", "Snap",
    "混元", "文心", "星火", "GLM", "MiniCPM", "Nemotron", "麒麟", "玄戒",
    "Devin", "Midjourney", "Stability", "Hugging Face", "Runway", "Perplexity",
    "Muse", "MiMo", "WorkBuddy", "Livo", "HiDream", "Ling", "MiniMax", "焱融",
]

ACTIONS = [
    "发布", "推出", "上线", "开源", "融资", "收购", "IPO", "上市", "诉讼",
    "起诉", "合作", "涨价", "降价", "宕机", "内测", "公测", "灰度", "预告",
    "更新", "重构", "升级", "关闭", "裁员", "道歉", "承认", "警告", "量产",
    "登顶", "亮相", "并入", "完成", "获投", "领投", "攻克", "验证", "曝光",
    "泄露", "商用", "成立", "刷新", "发售",
]

MONEY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:亿美元|亿欧元|亿元|万美元|万欧元|万元)")
TITLE_RE = re.compile(r"^###\s*(\d+)\s*[.、]?\s*(.+?)\s*$")
SEC_RE = re.compile(r"^##\s+(.+?)\s*$")
LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
BARE_URL_RE = re.compile(r"https?://[^\s)\]>，。；、]+")
DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
SRC_RE = re.compile(r"来源[：:**\s]*([^·|\n]+)")

EVENT_SIM_THRESHOLD = 0.45     # E7 事件链：标题 2-gram Jaccard 阈值
TITLE_SIM_THRESHOLD = 0.65     # E9 标题相似度阈值（厂商无关）
MAX_PER_VENDOR = 2             # E8 单期同厂商上限
PROGRESS_TAG = "【进展更新】"


# ══════════════════════════════════════════════════════════════════════
# 解析
# ══════════════════════════════════════════════════════════════════════
def _find_url(block):
    """从条目文本中取第一条真实文章链接（兼容 Markdown 链接与裸链接）。"""
    for m in LINK_RE.finditer(block):
        if m.group(1).strip() not in ("图片", "图", "原文-link"):
            return m.group(2).strip()
    m = BARE_URL_RE.search(block)
    return m.group(0).strip() if m else None


def _find_date(block):
    m = DATE_RE.search(block)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


def parse_report(text):
    """解析日报 → (preamble_lines, [ {header, items:[item,...]} ])

    item = {num, title, url, date, source, body, lines}
    """
    lines = text.split("\n")
    preamble, sections = [], []
    cur, item = None, None

    def close_item():
        nonlocal item
        if item is not None:
            if cur is not None:
                cur["items"].append(item)
            item = None

    for ln in lines:
        if SEC_RE.match(ln) and not ln.startswith("###"):
            close_item()
            cur = {"header": SEC_RE.match(ln).group(1), "items": []}
            sections.append(cur)
        elif ln.startswith("### "):
            close_item()
            if cur is None:                       # 容错：条目出现在分区标题之前
                cur = {"header": "", "items": []}
                sections.append(cur)
            item = {"title_line": ln, "lines": [ln]}
        elif item is not None:
            item["lines"].append(ln)
        elif cur is None:
            preamble.append(ln)
    close_item()

    for sec in sections:
        out = []
        for it in sec["items"]:
            m = TITLE_RE.match(it["title_line"])
            title = (m.group(2) if m else it["title_line"].lstrip("# ")).strip()
            block = "\n".join(it["lines"])
            body_lines = [
                l.strip() for l in it["lines"][1:]
                if l.strip() and not l.strip().startswith(">")
            ]
            body = "\n".join(body_lines)
            body = re.sub(r"^正文[：:]\s*", "", body).strip()
            out.append({
                "num": int(m.group(1)) if m else None,
                "title": title,
                "url": _find_url(block),
                "date": _find_date(block),
                "source": (SRC_RE.search(block).group(1).strip() if SRC_RE.search(block) else None),
                "body": body,
                "lines": it["lines"],
            })
        sec["items"] = out
    return preamble, sections


def render_report(preamble, sections):
    """按解析结构重新拼回 Markdown，条目连续重编号，空分区自动去掉。"""
    out = list(preamble)
    num = 0
    for sec in sections:
        if not sec["items"]:
            continue
        if sec["header"]:
            out.append("")
            out.append(f"## {sec['header']}")
        for it in sec["items"]:
            num += 1
            out.append("")
            out.append(f"### {num}. {it['title']}")
            for l in it["lines"][1:]:
                out.append(l)
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


# ══════════════════════════════════════════════════════════════════════
# 指纹
# ══════════════════════════════════════════════════════════════════════
def _grams(title):
    core = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", title or "")
    return {core[i:i + 2] for i in range(max(len(core) - 1, 0))}


def fingerprint(title, body=""):
    """事件指纹：(厂商集合, 动作集合, 金额集合, 标题 2-gram 集合)"""
    text = f"{title or ''} {body or ''}"
    vendors = {v for v in VENDORS if v in (title or "")}   # 厂商仅取标题
    actions = {a for a in ACTIONS if a in text}
    money = set(MONEY_RE.findall(text))
    return vendors, actions, money, _grams(title)


def is_dup_event(fp_new, fp_old):
    """是否同一事件链：厂商有交集 + 动作有交集 + (金额一致 或 标题用字高度重合)。"""
    v_n, a_n, m_n, g_n = fp_new
    v_o, a_o, m_o, g_o = fp_old
    if not (v_n & v_o) or not (a_n & a_o):
        return False
    if m_n & m_o:
        return True
    if g_n and g_o:
        return len(g_n & g_o) / len(g_n | g_o) >= EVENT_SIM_THRESHOLD
    return False


def title_similarity(a, b):
    """两标题的 2-gram Jaccard 相似度（厂商无关）。"""
    g1, g2 = _grams(a), _grams(b)
    if not g1 or not g2:
        return 0.0
    return len(g1 & g2) / len(g1 | g2)


# ══════════════════════════════════════════════════════════════════════
# 历史
# ══════════════════════════════════════════════════════════════════════
NAME_RE = re.compile(r"AI资讯24小时_(\d{4})年(\d{1,2})月(\d{1,2})日\.md")


def name_date(path):
    m = NAME_RE.search(os.path.basename(path))
    if not m:
        return None
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


class History(object):
    """全部历史日报的已覆盖集合。"""

    def __init__(self):
        self.urls = {}          # url -> 首次出现的文件名
        self.titles = []        # [(title, filename)]
        self.fps = []           # [(fingerprint, title, filename)]
        self.files = []         # 参与比对的历史文件名

    def __len__(self):
        return len(self.fps)


def load_history(report_dir, exclude=None, before=None):
    """读取报告目录下**全部**历史日报（不再只取最近 3 份）。

    exclude: 需排除的文件名集合（通常是今天待生成的文件）
    before:  只统计该日期之前的日报（默认不过滤）
    """
    exclude = set(exclude or ())
    h = History()
    paths = sorted(glob.glob(os.path.join(report_dir, "AI资讯24小时_*.md")))
    for p in paths:
        base = os.path.basename(p)
        if base in exclude:
            continue
        d = name_date(p)
        if d is None or (before is not None and d >= before):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        h.files.append(base)
        _, sections = parse_report(text)
        for sec in sections:
            for it in sec["items"]:
                if not it["title"]:
                    continue
                h.titles.append((it["title"], base))
                h.fps.append((fingerprint(it["title"], it["body"]), it["title"], base))
                if it["url"]:
                    h.urls.setdefault(it["url"], base)
    return h


# ══════════════════════════════════════════════════════════════════════
# 判定
# ══════════════════════════════════════════════════════════════════════
def _date_ok(d, day):
    if day is None:
        return True, None
    lo, hi = day - datetime.timedelta(days=1), day
    return (lo <= d <= hi), f"窗口 {lo} ~ {hi}"


def gate(text, history=None, day=None, expected_total=20, expected_sections=None):
    """逐项校验，返回 (errors, warnings, items, sections)。

    history 为 History 实例或 None；day 为日报日期（None 则跳过 E4）。
    """
    errors, warnings = [], []
    history = history or History()
    _, sections = parse_report(text)
    items = [it for sec in sections for it in sec["items"]]

    # E5 必备要素
    for i, it in enumerate(items, 1):
        missing = []
        if not it["title"]:
            missing.append("标题")
        if not it["url"]:
            missing.append("原文链接")
        if not it["source"]:
            missing.append("来源")
        if not it["body"]:
            missing.append("正文")
        if missing:
            errors.append(f"E5 第 {i} 条缺失要素：{'/'.join(missing)} → {it['title'][:36]}")

    # E1 / E6 数量与分区
    if expected_total is not None and len(items) != expected_total:
        errors.append(f"E1 条目数为 {len(items)}，要求恰为 {expected_total}")
    if expected_sections is not None:
        counts = [len(sec["items"]) for sec in sections]
        if counts != expected_sections:
            errors.append(f"E6 分类分布为 {counts}，要求 {expected_sections}")

    # E2 期内链接重复
    seen = {}
    for i, it in enumerate(items, 1):
        u = it["url"]
        if not u:
            continue
        if u in seen:
            errors.append(f"E2 本期重复链接（第 {seen[u]} 条 与 第 {i} 条）：{u}")
        else:
            seen[u] = i

    # E3 跨历史链接重复
    for i, it in enumerate(items, 1):
        u = it["url"]
        if u and u in history.urls:
            msg = (f"E3 与往期重复链接（往期 {history.urls[u]}）：{u} → {it['title'][:34]}")
            if PROGRESS_TAG in (it["title"] or ""):
                warnings.append("已标注【进展更新】，不阻断 —— " + msg)
            else:
                errors.append(msg)

    # E7a 期内事件链重复
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            fa = fingerprint(items[i]["title"], items[i]["body"])
            fb = fingerprint(items[j]["title"], items[j]["body"])
            if is_dup_event(fa, fb):
                errors.append(f"E7 本期事件链重复：第 {i+1} 条「{items[i]['title'][:24]}」"
                              f" 与 第 {j+1} 条「{items[j]['title'][:24]}」疑似同一事件")

    # E7b 跨历史事件链重复
    for i, it in enumerate(items, 1):
        fp = fingerprint(it["title"], it["body"])
        for hfp, htitle, hname in history.fps:
            if is_dup_event(fp, hfp):
                msg = f"E7 事件链重复（往期 {hname}「{htitle[:24]}」）：{it['title'][:32]}"
                if PROGRESS_TAG in (it["title"] or ""):
                    warnings.append("已标注【进展更新】，不阻断 —— " + msg)
                else:
                    errors.append(f"第 {i} 条 " + msg)
                break

    # E9 标题相似度（厂商无关，兜 E7 的盲区）
    for i, it in enumerate(items, 1):
        for htitle, hname in history.titles:
            sim = title_similarity(it["title"], htitle)
            if sim >= TITLE_SIM_THRESHOLD:
                msg = (f"E9 标题高度相似（{sim:.2f}，往期 {hname}「{htitle[:24]}」）："
                       f"{it['title'][:30]}")
                if PROGRESS_TAG in (it["title"] or ""):
                    warnings.append("已标注【进展更新】，不阻断 —— " + msg)
                else:
                    errors.append(f"第 {i} 条 " + msg)
                break

    # E8 厂商集中度
    vc = {}
    for it in items:
        for v in {v for v in VENDORS if v in (it["title"] or "")}:
            vc[v] = vc.get(v, 0) + 1
    for v, c in sorted(vc.items(), key=lambda x: -x[1]):
        if c > MAX_PER_VENDOR:
            errors.append(f"E8 厂商刷屏：{v} 本期出现 {c} 条（要求 ≤{MAX_PER_VENDOR}）")

    # E4 时间窗口
    for i, it in enumerate(items, 1):
        if it["date"] is None:
            warnings.append(f"E4 第 {i} 条未标注明确日期（{it['title'][:30]}）")
            continue
        ok, win = _date_ok(it["date"], day)
        if not ok:
            errors.append(f"E4 第 {i} 条超窗（发布 {it['date']}，{win}）：{it['title'][:36]}")

    return errors, warnings, items, sections


# ══════════════════════════════════════════════════════════════════════
# 生成阶段自愈：确定性过滤
# ══════════════════════════════════════════════════════════════════════
def filter_report(text, history=None, day=None, max_per_vendor=MAX_PER_VENDOR):
    """按去重规则**确定性丢弃**违规条目，并连续重编号。

    返回 (new_text, kept_items, dropped) ；dropped = [(item, 原因), ...]
    过滤顺序即条目出现顺序（保留靠前、信息更完整的条目）。
    """
    history = history or History()
    preamble, sections = parse_report(text)
    kept, dropped = [], []
    kept_urls = {}
    vendor_count = {}

    for sec in sections:
        survivors = []
        for it in sec["items"]:
            reason = _violation(it, history, kept, kept_urls, vendor_count, day, max_per_vendor)
            if reason:
                dropped.append((it, reason))
            else:
                survivors.append(it)
                if it["url"]:
                    kept_urls[it["url"]] = it["title"]
                for v in {v for v in VENDORS if v in (it["title"] or "")}:
                    vendor_count[v] = vendor_count.get(v, 0) + 1
                kept.append(it)
        sec["items"] = survivors

    return render_report(preamble, sections), kept, dropped


def _violation(it, history, kept, kept_urls, vendor_count, day, max_per_vendor):
    """返回违规原因；无违规返回 None。"""
    title = it["title"] or ""
    progress = PROGRESS_TAG in title

    if not it["url"]:
        return "缺少原文链接"

    if it["url"] in kept_urls:
        return "本期链接重复"
    if it["url"] in history.urls and not progress:
        return f"与往期链接重复（{history.urls[it['url']]}）"

    fp = fingerprint(title, it["body"])

    # 期内
    for k in kept:
        if is_dup_event(fp, fingerprint(k["title"], k["body"])) and not progress:
            return f"本期事件重复（{k['title'][:20]}）"
        if title_similarity(title, k["title"]) >= TITLE_SIM_THRESHOLD and not progress:
            return f"本期标题相似（{k['title'][:20]}）"

    # 跨历史
    for hfp, htitle, hname in history.fps:
        if is_dup_event(fp, hfp) and not progress:
            return f"历史事件重复（{hname}：{htitle[:20]}）"
    for htitle, hname in history.titles:
        if title_similarity(title, htitle) >= TITLE_SIM_THRESHOLD and not progress:
            return f"历史标题相似（{hname}：{htitle[:20]}）"

    # 厂商集中度
    if not progress:
        for v in {v for v in VENDORS if v in title}:
            if vendor_count.get(v, 0) >= max_per_vendor:
                return f"厂商集中度超限（{v} 已 {vendor_count[v]} 条）"

    # 时间窗
    if day is not None and it["date"] is not None:
        ok, win = _date_ok(it["date"], day)
        if not ok:
            return f"超出时间窗（{it['date']}，{win}）"

    return None
