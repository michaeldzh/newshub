---
name: newshub
description: 每天定时生成「AI 资讯 24 小时」日报（Claude 联网搜索筛选 20 条全球 AI 动态），并通过 163 邮箱推送到指定收件箱。Use when: (1) 生成每日 AI 资讯日报, (2) 把 AI 资讯推送到邮箱, (3) 在 GitHub Actions 上自动运行 AI 新闻聚合。
license: MIT
---

# AI 资讯日报 Skill

每天自动搜索过去 24 小时全球 AI 领域的重要动态（AI 技术 / AI 应用 / AI 行业），
筛选 20 条有价值的国内外资讯，生成 HTML 报告并通过 163 邮箱推送。

## 工作流程

1. `generate_ai_news.py`：调用 Claude API（启用 web_search 工具）联网搜索并生成
   `index.html`（20 条 AI 资讯，含标题 / 摘要 / 发布日期 / 来源 / 原文链接）。
2. `push_email.py`：读取 `index.html`，通过 163 SMTP 推送到邮箱（HTML 正文 + 附件）。

## 环境变量 / Secrets（全部通过环境变量注入，绝不硬编码）

| 变量 | 必填 | 说明 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 是 | Claude API Key（用于联网搜索生成报告） |
| `ANTHROPIC_BASE_URL` | 否 | 自定义 API 网关（默认 https://api.anthropic.com） |
| `ANTHROPIC_MODEL` | 否 | 模型名（默认 claude-sonnet-4-5） |
| `NEWS_SMTP_USER` | 否 | 发件人（默认 newshub01@163.com） |
| `NEWS_SMTP_TO` | 否 | 收件人（默认 newshub01@163.com） |
| `NEWS_SMTP_AUTH` | 是 | 163 邮箱客户端授权码 |

## 本地运行

```bash
cd skills/newshub
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
export NEWS_SMTP_AUTH=...
python generate_ai_news.py      # 生成 index.html
python push_email.py index.html # 推送
```

## GitHub Actions 定时

由 `.github/workflows/news-aggregator.yml` 每天定时触发（默认北京时间 08:00），
自动完成「生成报告 → 推送邮箱」全流程，所有密钥通过仓库 Secrets 注入。
