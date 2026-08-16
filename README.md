# newshub · 每日 AI 资讯日报

一个自包含的 GitHub 仓库 Skill：**每天自动检索过去 24 小时全球 AI 动态，筛选 20 条有价值的中外信息，推送至 163 邮箱**。

> 本仓库已完全替换原 newshub 项目，与旧的 Claude Agent SDK / 天行数据聚合无任何关系。

## 结构
```
skills/newshub/
  generate.py         # 联网检索 + 生成 AI资讯24小时_YYYY年M月D日.md / index.html
  push_email.py       # 经 163 SMTP 推送最新报告（HTML 正文 + 附件）
  requirements.txt
  SKILL.md
.github/workflows/    # 定时调度（见下）
```

## 报告内容
每条资讯包含：**标题 / 摘要 / 发布日期 / 来源 / 原文链接**，分「AI 技术 / AI 应用 / AI 行业动态」三栏，合计 20 条。

## 定时运行
由 GitHub Actions 每天 **北京时间 07:00**（UTC 23:00 前一日，cron `0 23 * * *`）触发（`.github/workflows/ai-news.yml`），也可在 Actions 页手动 `Run workflow` 立即测试。

## 去重
`generate.py` 生成前会读取本目录最近 3 份 `AI资讯24小时_*.md`，汇总「事件标题 + 原文链接」作为"已覆盖集合"注入提示词，强制**跨日 + 本日内去重**，仅收录过去 24 小时内新闻。生成的日报会提交回仓库，供次日跨日去重使用。

## 密钥（全部走 Secrets，零硬编码）
| Secret | 必填 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 是 | 生成报告用 |
| `ANTHROPIC_BASE_URL` | 否 | 默认 https://api.anthropic.com |
| `ANTHROPIC_MODEL` | 否 | 模型名 |
| `NEWS_SMTP_AUTH` | 是 | 163 邮箱授权码 |
| `NEWS_SMTP_USER` | 否 | 默认 newshub01@163.com |
| `NEWS_SMTP_TO` | 否 | 默认 newshub01@163.com |

## 本地手动运行
```bash
pip install -r skills/newshub/requirements.txt
cd skills/newshub
export ANTHROPIC_API_KEY=xxx
python generate.py
export NEWS_SMTP_AUTH=xxxx
python push_email.py
```
