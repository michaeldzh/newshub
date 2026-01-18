# Claude Code中使用全球新闻汇聚Skill

## 🎯 快速使用指南

### 使用 /newshub 命令（推荐）

在Claude Code中输入命令：

```
/newshub
```

Claude会自动：
- 检查配置文件
- 调用新闻聚合脚本
- 生成HTML报告
- 返回报告位置

## 📋 Skill工作流程

```
用户请求
    ↓
Claude识别skill触发条件
    ↓
加载api-config.json配置
    ↓
调用news_aggregator.py脚本
    ↓
获取国际新闻（10条）
    ↓
获取国内新闻（10条）
    ↓
使用WebSearch工具搜索详细内容
    ↓
生成HTML报告
    ↓
返回报告文件路径
```

## 🔧 配置步骤

### 第1步：准备API密钥

获取以下API的密钥：

**国际新闻API选项：**
- NewsAPI (https://newsapi.org/) - 推荐
- The Guardian API
- New York Times API

**国内新闻API选项：**
- 新浪新闻API
- 腾讯新闻API
- 网易新闻API

### 第2步：创建配置文件

在skill目录下创建 `api-config.json`：

```json
{
  "international_api": {
    "name": "NewsAPI",
    "endpoint": "https://newsapi.org/v2/top-headlines",
    "method": "GET",
    "auth_type": "api_key",
    "auth_header": "YOUR_NEWSAPI_KEY_HERE",
    "params": {
      "country": "us",
      "sortBy": "popularity",
      "pageSize": 10
    },
    "response_format": {
      "headlines_path": "articles",
      "title_field": "title",
      "description_field": "description",
      "url_field": "url",
      "image_field": "urlToImage",
      "source_field": "source.name",
      "published_at_field": "publishedAt"
    }
  },
  "domestic_api": {
    "name": "Domestic News API",
    "endpoint": "https://your-api.com/news",
    "method": "GET",
    "auth_type": "bearer",
    "auth_header": "YOUR_BEARER_TOKEN_HERE",
    "params": {
      "region": "domestic",
      "limit": 10
    },
    "response_format": {
      "headlines_path": "data.articles",
      "title_field": "title",
      "description_field": "summary",
      "url_field": "link",
      "image_field": "image",
      "source_field": "source",
      "published_at_field": "timestamp"
    }
  },
  "output": {
    "report_filename": "global_news_report.html",
    "report_title": "全球新闻汇总",
    "include_images": true,
    "include_timestamps": true
  }
}
```

### 第3步：安装依赖

```bash
pip install -r requirements.txt
```

## 📊 输出示例

生成的HTML报告包含：

```
┌─────────────────────────────────────┐
│  🌍 全球新闻汇总                     │
│  生成时间: 2024-01-17 10:30:00      │
│                                     │
│  总新闻数: 20  国际: 10  国内: 10   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🌐 国际                             │
│ 标题: Breaking News Title           │
│ 来源: Reuters                       │
│ 日期: 2024-01-17                    │
│ 描述: News description...           │
│ [阅读全文 →]                        │
└─────────────────────────────────────┘

... (共20条新闻卡片)
```

## 🚀 高级用法

### 自定义新闻数量

编辑脚本中的限制：

```python
for item in headlines[:15]:  # 改为15条
```

### 自定义输出样式

修改HTML中的CSS部分：

```python
# 改变颜色主题
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

# 改变卡片布局
grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
```

### 定时运行

使用cron或任务计划程序定时生成报告：

```bash
# Linux/Mac - 每天早上8点运行
0 8 * * * python /path/to/enhanced_news_aggregator.py /path/to/api-config.json

# Windows - 使用任务计划程序
schtasks /create /tn "NewsAggregator" /tr "python C:\path\to\script.py" /sc daily /st 08:00
```

## 🔍 Web Search集成

增强版本会自动：

1. 获取每条新闻的标题
2. 使用Claude的WebSearch工具搜索详细内容
3. 在HTML中显示搜索结果

**示例：**
```
标题: "AI突破性进展"
↓
WebSearch搜索: "AI breakthrough 2024"
↓
获取详细内容并显示在报告中
```

## 🐛 常见问题

**Q: 如何更改报告的外观？**
A: 编辑 `enhanced_news_aggregator.py` 中的CSS样式部分

**Q: 支持多少条新闻？**
A: 默认20条（国际10+国内10），可自定义

**Q: 如何处理API错误？**
A: 脚本会自动处理错误并显示详细信息

**Q: 报告保存在哪里？**
A: 默认保存为 `global_news_report.html`，可在配置中修改

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| SKILL.md | Skill定义（Claude Code识别） |
| api-config.json | API配置文件 |
| api-config-example.json | 配置示例 |
| news_aggregator.py | 基础聚合脚本 |
| enhanced_news_aggregator.py | 增强版（推荐） |
| claude_news_aggregator.py | Claude集成版 |
| requirements.txt | Python依赖 |
| README.md | 详细文档 |

## ✅ 检查清单

在使用前确认：

- [ ] 获取了API密钥
- [ ] 创建了 `api-config.json`
- [ ] 安装了依赖 (`pip install -r requirements.txt`)
- [ ] 测试了API连接
- [ ] 验证了响应格式

## 🎓 学习资源

- [NewsAPI文档](https://newsapi.org/docs)
- [Claude Code文档](https://code.claude.com/docs)
- [Skill创建指南](https://claude.com/blog/how-to-create-skills)

## 📞 获取帮助

如遇问题：

1. 检查 `api-config.json` 配置
2. 验证API密钥有效性
3. 查看脚本输出的错误信息
4. 参考README.md中的故障排除部分
