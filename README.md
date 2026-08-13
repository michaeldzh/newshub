# 🤖 NewsHub - AI 资讯日报

每天定时搜索过去 24 小时全球 AI 领域的重要动态，筛选 20 条有价值的国内外资讯，
生成 HTML 报告并通过 163 邮箱推送到你的收件箱。

## ✨ 特性

- 🔍 **Claude 联网搜索**：使用 Claude API（web_search 工具）实时检索全球 AI 资讯
- 📰 **20 条精选**：覆盖 AI 技术 / AI 应用 / AI 行业，国内外混合，多源去重
- ⏰ **自动定时**：GitHub Actions 每天定时生成并推送
- 📧 **邮箱推送**：报告以 HTML 正文 + 附件形式发送到 163 邮箱
- 🔐 **密钥安全**：所有授权码 / API Key 均通过 GitHub Secrets（环境变量）注入，不落盘

## 🚀 快速开始

在仓库 **Settings → Secrets and variables → Actions** 中添加：

| Secret | 必填 | 说明 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | 是 | Claude API Key（生成报告用） |
| `ANTHROPIC_BASE_URL` | 否 | 自定义 API 网关 |
| `ANTHROPIC_MODEL` | 否 | 模型（默认 claude-sonnet-4-5） |
| `NEWS_SMTP_AUTH` | 是 | 163 邮箱客户端授权码 |
| `NEWS_SMTP_TO` | 否 | 收件邮箱（默认 newshub01@163.com） |

## 📁 项目结构

```
newshub/
├── .github/
│   └── workflows/
│       └── news-aggregator.yml    # 定时工作流（生成 + 推送）
├── skills/
│   └── newshub/
│       ├── generate_ai_news.py     # Claude 联网搜索生成 AI 资讯报告
│       ├── push_email.py           # 163 邮箱推送
│       └── requirements.txt        # Python 依赖
└── README.md
```

## 🔧 本地运行

```bash
cd skills/newshub
pip install -r requirements.txt
export ANTHROPIC_API_KEY="..."
export NEWS_SMTP_AUTH="..."
python generate_ai_news.py
python push_email.py index.html
```

## 📄 许可证

MIT License
