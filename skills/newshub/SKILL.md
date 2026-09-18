---
name: ai-news-email-push
description: 生成并推送每日 AI 资讯日报。检索过去 24 小时全球 AI 动态（技术/应用/行业），筛选 20 条，强制跨日+本日内去重，经 163 邮箱定时推送。每天北京时间 08:00 自动运行。
---

# 每日 AI 资讯日报（自包含 Skill）

## 功能
1. **generate.py** — 调用大模型 + 联网检索，生成 `AI资讯24小时_YYYY年M月D日.md` 与 `index.html`（20 条，AI 技术 7 / AI 应用 7 / AI 行业动态 6）。
2. **dedup.py** — 去重核心：解析日报、载入全量历史、事件指纹判定、确定性过滤。
3. **check_report.py** — 成稿硬校验（E1–E9），CI 与本地通用。
4. **push_email.py** — 将报告经 163 SMTP 推送（HTML 正文 + Markdown 附件）。

## 运行方式
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=xxx        # 生成报告用
export ANTHROPIC_BASE_URL=...        # 可选
export ANTHROPIC_MODEL=...           # 可选
python generate.py

export REPORT_DIR=.                 # 可选，日报目录（默认脚本所在目录）
python check_report.py              # 成稿校验，FAIL 退出码 1

export NEWS_SMTP_AUTH=xxxx          # 163 授权码（必填）
export NEWS_SMTP_TO=newshub01@163.com
python push_email.py index.html
```

## 定时
通过 GitHub Actions（`.github/workflows/ai-news.yml`）每天**北京时间 08:00**（UTC 00:00）触发；亦可 `workflow_dispatch` 手动触发。密钥全部来自仓库 Secrets，不落盘。

## 去重机制（v2 · 确定性）
> v1 的去重是"软"的：只读最近 3 份日报塞进提示词，且工作流从未把日报提交回仓库，
> 那 3 份永远是 0 份 → 跨日去重完全空转，同一事件隔几天就换个链接重发。v2 改为代码强制。

**三层保障**

1. **全量历史基线** — `dedup.load_history()` 读取报告目录下**全部** `AI资讯24小时_*.md`，
   汇总链接、标题与事件指纹（不再只取最近 3 份）。这条依赖工作流的
   `Commit report back` 步骤把每天的日报提交回仓库，缺了它基线就永远是空的。

2. **确定性闸门** — `dedup.filter_report()` 在成稿后硬性剔除违规条目，不看模型脸色：
   - `E2` 期内链接重复 → 剔除
   - `E3` 与全部历史链接重复 → 剔除（标 `【进展更新】` 者保留）
   - `E7` 事件链指纹重复（厂商×动作×金额 / 标题 2-gram ≥0.45，期内 + 全部历史）→ 剔除
   - `E9` 标题相似度重复（2-gram Jaccard ≥0.65，**厂商无关**，兜 E7 漏网的"标题里没有厂商名"条目）→ 剔除
   - `E8` 单期同一厂商 >2 条 → 剔除超出部分
   - `E4` 发布日期超出 `[D-1, D]` → 剔除
   - `E5` 缺标题/链接/来源/正文 → 剔除

3. **缺口自愈** — 被剔除的空位按分区向模型追加补稿（最多 3 轮），补稿时附上
   "已保留 + 已剔除 + 往期"的禁用清单。**凑不满 20 条或仍有硬错误就退出码 1**，
   当天不产出、不推送 —— 宁可空一天，也不推重复内容。

**放行通道**：同一事件若确有实质性新进展（新版本 / 新金额 / 新状态），标题以
`【进展更新】` 开头即可放行，闸门会降级为 WARN 记录在案。禁止用它包装旧闻。

## 环境变量
| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 是 | 生成报告用 |
| `ANTHROPIC_BASE_URL` | 否 | 自定义 API 网关（默认官方） |
| `ANTHROPIC_MODEL` | 否 | 模型名 |
| `TAVILY_API_KEY` | 否 | 检索源；不填则用免 key 的 Google News / HN |
| `REPORT_DIR` | 否 | 日报目录（默认脚本所在目录） |
| `HISTORY_PROMPT_LIMIT` | 否 | 提示词注入的历史条目上限（默认 240） |
| `MAX_REPAIR_ROUNDS` | 否 | 补稿轮数上限（默认 3） |
| `NEWS_SMTP_USER` | 否 | 发件人，默认 newshub01@163.com |
| `NEWS_SMTP_TO` | 否 | 收件人，默认 newshub01@163.com |
| `NEWS_SMTP_AUTH` | 是 | 163 邮箱授权码 |
