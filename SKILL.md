---
name: ai-news-email-push
description: 生成并推送每日 AI 资讯日报。检索过去 24 小时全球 AI 动态（技术/应用/行业），筛选 20 条，强制跨日+本日内去重，经 163 邮箱定时推送。每天北京时间 07:00 自动运行。
---

# 每日 AI 资讯日报（自包含 Skill）

完全替换原 newshub 项目，与旧版 Claude Agent SDK / 天行数据聚合无任何关系。

## 功能
1. **generate.py** — 调用大模型 + web_search 联网检索，生成 `AI资讯24小时_YYYY年M月D日.md` 与 `index.html`（20 条，含标题/摘要/发布日期/来源/原文链接）。
2. **push_email.py** — 将最新报告经 163 SMTP 推送至指定邮箱（HTML 正文 + 原文件附件）。

## 运行方式
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=xxx        # 生成报告用
export ANTHROPIC_BASE_URL=...        # 可选，默认 https://api.anthropic.com
export ANTHROPIC_MODEL=...           # 可选
python generate.py
export NEWS_SMTP_AUTH=xxxx          # 163 授权码（必填）
export NEWS_SMTP_TO=newshub01@163.com
python push_email.py
```

## 定时
通过 GitHub Actions（`.github/workflows/ai-news.yml`）每天**北京时间 07:00**（UTC 23:00 前一日）触发；亦可 `workflow_dispatch` 手动触发。密钥全部来自仓库 Secrets，不落盘。

## 去重（已内置）
`generate.py` 在生成前会读取本目录最近 3 份 `AI资讯24小时_*.md`，汇总「事件标题 + 原文链接」作为"已覆盖集合"，注入大模型提示词，要求：
- 跨日去重：已覆盖集合中的事件一律不重复收录（仅实质性新进展才收为"进展更新"）；
- 本日内去重：同事件只保留一条最完整报道；
- 时间窗口：仅收录过去 24 小时内新闻。
生成的日报会提交回仓库（`Commit report back` 步骤），供次日跨日去重使用。

## 环境变量
| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 是 | 生成报告用 |
| `ANTHROPIC_BASE_URL` | 否 | 自定义 API 网关（默认官方） |
| `ANTHROPIC_MODEL` | 否 | 模型名 |
| `NEWS_SMTP_USER` | 否 | 发件人，默认 newshub01@163.com |
| `NEWS_SMTP_TO` | 否 | 收件人，默认 newshub01@163.com |
| `NEWS_SMTP_AUTH` | 是 | 163 邮箱授权码 |
