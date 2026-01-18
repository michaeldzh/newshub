# 🌍 NewsHub - 全球新闻聚合器

自动聚合国际和国内新闻，使用 Claude Agent SDK 智能生成每日新闻报告。

## ✨ 特性

- 🤖 **Claude AI 驱动**：使用 Claude Agent SDK 智能执行任务
- 🌐 **双源新闻**：聚合国际（NewsAPI）和国内（天行数据）新闻
- ⏰ **自动定时**：每天自动生成最新新闻报告
- 📱 **响应式设计**：左右分栏布局，移动端自适应
- 🚀 **GitHub Pages**：自动部署到 GitHub Pages

## 🚀 快速开始

### 1. 配置 GitHub Secrets

在仓库设置中添加以下 Secrets：

| Secret 名称 | 说明 |
|------------|------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 |
| `ANTHROPIC_BASE_URL` | Claude API 端点 |
| `NEWSAPI_KEY` | NewsAPI 密钥 |
| `TIANAPI_KEY` | 天行数据密钥 |

### 2. 启用 GitHub Pages

1. 进入仓库 Settings → Pages
2. Source 选择 `gh-pages` 分支
3. 保存设置

### 3. 运行 Workflow

- 自动运行：每天 UTC 0:00（北京时间 8:00）
- 手动运行：Actions → Daily News Aggregator → Run workflow

## 📁 项目结构

```
newshub/
├── .github/
│   └── workflows/
│       └── news-aggregator.yml    # GitHub Actions 工作流
├── skills/
│   └── newshub/
│       ├── enhanced_news_aggregator.py  # 新闻聚合脚本
│       ├── run_with_claude.py           # Claude Agent 脚本
│       ├── requirements.txt             # Python 依赖
│       └── api-config.example.json      # API 配置模板
└── README.md
```

## 🔧 本地开发

### 安装依赖

```bash
cd skills/newshub
pip install -r requirements.txt
```

### 配置 API

复制配置模板并填入你的 API 密钥：

```bash
cp api-config.example.json api-config.json
# 编辑 api-config.json，填入真实的 API 密钥
```

### 运行脚本

```bash
# 方式 1：直接运行聚合脚本
python enhanced_news_aggregator.py api-config.json

# 方式 2：使用 Claude Agent
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_BASE_URL="your-api-endpoint"
python run_with_claude.py
```

## 📊 使用的 API

- **NewsAPI**：国际新闻源 - https://newsapi.org
- **天行数据**：国内新闻源 - https://www.tianapi.com
- **Claude API**：AI 智能执行 - https://www.anthropic.com

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
