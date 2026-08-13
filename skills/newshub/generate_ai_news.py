#!/usr/bin/env python3
"""
AI 资讯日报生成器

调用 Claude API（启用 web_search 工具）搜索过去 24 小时全球 AI 领域重要动态，
筛选 20 条国内外有价值的资讯，生成一份完整的 HTML 报告（index.html）。

依赖的环境变量（全部通过 Secrets / 环境变量注入，绝不硬编码）：
  ANTHROPIC_API_KEY   必填，Claude API Key
  ANTHROPIC_BASE_URL  可选，自定义 API 网关（兼容 OpenAI 风格代理时常设）
  ANTHROPIC_MODEL     可选，模型名（默认 claude-sonnet-4-5）
  TZ                   可选，时区（默认 Asia/Shanghai）
"""

import os
import sys
import json
import re
import requests
from datetime import datetime, timezone, timedelta

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
OUTPUT = os.environ.get("REPORT_PATH", "index.html")

SYSTEM_PROMPT = (
    "你是一名资深 AI 资讯编辑。请基于联网搜索（web_search 工具）获取过去 24 小时内"
    "全球 AI 领域的重要动态，覆盖 AI 技术、AI 应用、AI 行业动态，侧重技术和应用。"
    "筛选 20 条有价值的国内外信息，尽量多渠道（厂商官网 + 主流媒体）。"
    "不要编造链接，链接必须来自搜索结果原文。"
)

USER_PROMPT = (
    "请搜索并整理「过去 24 小时」全球 AI 领域的重要资讯，要求：\n"
    "1. 共 20 条，国内外混合（可含少量重磅行业/技术突破）。\n"
    "2. 每条必须包含：标题、摘要（2-4 句）、发布日期、来源（媒体/厂商名）、原文链接。\n"
    "3. 链接必须是搜索结果中真实存在的原文 URL，不要生成伪造链接。\n"
    "4. 按「AI 技术 / AI 应用 / AI 行业」三栏分组，每组数量合理。\n\n"
    "请直接输出一份完整的 HTML 文件（从 <!DOCTYPE html> 开始，到 </html> 结束），"
    "中文、响应式布局，顶部显示报告标题与生成日期，每条资讯用卡片展示"
    "（标题加粗、摘要、来源、日期、可点击的原文链接）。不要输出任何 HTML 之外的解释文字。"
)


def extract_html(text: str) -> str:
    m = re.search(r"<!DOCTYPE html.*?</html>", text, re.IGNORECASE | re.DOTALL)
    return m.group(0) if m else ""


def main():
    if not API_KEY:
        print("ERROR: 未设置 ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)

    bj = timezone(timedelta(hours=8))
    today = datetime.now(bj).strftime("%Y年%m月%d日")
    system = SYSTEM_PROMPT + f"\n报告标题固定为：AI 资讯 24 小时 | {today}"

    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 8000,
        "system": system,
        "messages": [{"role": "user", "content": USER_PROMPT}],
        "tools": [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 12,
            }
        ],
    }

    print("正在调用 Claude 生成 AI 资讯日报（含联网搜索）...")
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/messages",
            headers=headers,
            json=payload,
            timeout=300,
        )
    except Exception as e:
        print(f"ERROR: 请求失败 {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"ERROR: API {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    text = "".join(
        b.get("text", "")
        for b in data.get("content", [])
        if b.get("type") == "text"
    )
    html = extract_html(text)

    if not html:
        print("ERROR: 未能从响应中提取 HTML 报告", file=sys.stderr)
        print("DEBUG tail:", text[-800:], file=sys.stderr)
        sys.exit(1)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK: AI 资讯报告已生成 -> {OUTPUT} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
