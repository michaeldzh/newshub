#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 AI 资讯生成器（仓库内自包含版本）

- 通过 Anthropic Messages API + web_search 工具联网检索「过去 24 小时」全球 AI 动态
- 筛选 20 条有价值的中外信息（技术 / 应用 / 行业，侧重技术与应用）
- 输出 Markdown: AI资讯24小时_YYYY年M月D日.md 与 index.html
- 所有密钥经环境变量注入，不硬编码

环境变量：
  ANTHROPIC_API_KEY   必填，调用方注入（仓库 Secrets）
  ANTHROPIC_BASE_URL  可选，自定义 API 网关，默认 https://api.anthropic.com
  ANTHROPIC_MODEL     可选，模型名，默认 claude-sonnet-4-5-20250929
"""

import os
import re
import json
import base64
import datetime
import html as _html
import requests

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BASE_URL = (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-5-20250929"

if not API_KEY:
    raise SystemExit("ERROR: 环境变量 ANTHROPIC_API_KEY 未设置")

DATE = datetime.date.today()
DATE_STR = f"{DATE.year}年{DATE.month}月{DATE.day}日"
OUT_MD = f"AI资讯24小时_{DATE_STR}.md"

PROMPT = f"""你是资深 AI 资讯编辑。请使用 web_search 工具，检索「过去 24 小时」之内全球 AI 领域的重要动态，
覆盖 AI 技术、AI 应用、AI 行业动态，侧重技术和应用。

要求：
1. 尽量多渠道：厂商官网（OpenAI、Google DeepMind、Anthropic、Meta、NVIDIA、字节跳动、阿里、DeepSeek、腾讯等）与主流科技媒体（TechCrunch、The Verge、VentureBeat、机器之心、量子位等）。
2. 筛选 20 条有价值的国内外信息，避免重复与低质软文。
3. 每条信息必须包含：标题、摘要、发布日期、来源、原文链接。
4. 按「一、AI 技术 / 二、AI 应用 / 三、AI 行业动态」三栏组织（每栏若干条，合计 20 条）。
5. 直接输出 Markdown 正文（从一级标题开始），不要额外解释或前言。

输出示例结构：
# AI 资讯 24 小时 | {DATE_STR}
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

WS_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 24}


def call_api(messages):
    resp = requests.post(
        f"{BASE_URL}/v1/messages",
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 8000,
            "tools": [WS_TOOL],
            "messages": messages,
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise SystemExit(f"ERROR: API 调用失败 {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def main():
    messages = [{"role": "user", "content": PROMPT}]
    final_text = ""
    for _ in range(10):
        resp = call_api(messages)
        messages.append({"role": "assistant", "content": resp["content"]})
        text = "".join(b.get("text", "") for b in resp["content"] if b.get("type") == "text")
        if text.strip():
            final_text = text
        if resp.get("stop_reason") != "tool_use":
            break
        # web_search 由 Anthropic 服务端执行，这里回执确认即可
        tool_results = []
        for b in resp["content"]:
            if b.get("type") == "tool_use":
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": b["id"],
                    "content": "search completed",
                })
        if not tool_results:
            break
        messages.append({"role": "user", "content": tool_results})

    if not final_text.strip():
        raise SystemExit("ERROR: 模型未返回正文，可能当前网关不支持 web_search 工具，请检查 ANTHROPIC_BASE_URL")

    # 规整：若模型带了一级标题则用之，否则补一个
    if not final_text.lstrip().startswith("#"):
        final_text = f"# AI 资讯 24 小时 | {DATE_STR}\n\n" + final_text

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(final_text)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(md_to_html(final_text, DATE_STR))
    print(f"OK: 已生成 {OUT_MD} ({len(final_text)} 字符)")


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


if __name__ == "__main__":
    main()
