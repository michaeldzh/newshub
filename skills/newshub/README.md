# 全球新闻汇聚 Skill 使用指南

## 📋 项目概述

这是一个为Claude Code设计的全球新闻汇聚skill，能够自动从国际和国内新闻API获取最新热点新闻，并生成专业的HTML报告。

## 🎯 功能特性

- ✅ 自动从两个API获取新闻（国际10条 + 国内10条）
- ✅ 集成Web Search工具获取详细内容
- ✅ 生成美观的HTML报告
- ✅ 响应式设计，支持移动设备
- ✅ 新闻分类标签（国际/国内）
- ✅ 自动时间戳和统计信息

## 📁 项目结构

```
global-news-aggregator/
├── SKILL.md                          # Skill定义文件（Claude Code识别）
├── api-config-example.json           # API配置示例
├── news_aggregator.py                # 基础新闻聚合脚本
├── enhanced_news_aggregator.py       # 增强版本（含Web Search集成）
├── README.md                         # 本文件
└── requirements.txt                  # Python依赖
```

## 🚀 快速开始

### 第一步：配置API

1. 获取你的新闻API密钥：
   - 国际新闻API（如NewsAPI、Guardian等）
   - 国内新闻API（如新浪新闻、腾讯新闻等）

2. 创建 `api-config.json` 文件：

```json
{
  "international_api": {
    "name": "NewsAPI",
    "endpoint": "https://newsapi.org/v2/top-headlines",
    "method": "GET",
    "auth_type": "api_key",
    "auth_header": "YOUR_NEWSAPI_KEY",
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
    "auth_header": "YOUR_BEARER_TOKEN",
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

### 第二步：安装依赖

```bash
pip install requests
```

### 第三步：运行脚本

**基础版本：**
```bash
python news_aggregator.py api-config.json
```

**增强版本（推荐）：**
```bash
python enhanced_news_aggregator.py api-config.json
```

**指定输出文件：**
```bash
python enhanced_news_aggregator.py api-config.json output/my_report.html
```

## 🔧 API配置详解

### 支持的认证方式

- `api_key`: API密钥认证（添加到URL参数）
- `bearer`: Bearer Token认证（添加到Authorization头）
- `none`: 无认证

### 响应格式配置

| 字段 | 说明 | 示例 |
|------|------|------|
| `headlines_path` | JSON路径到新闻数组 | `articles` 或 `data.articles` |
| `title_field` | 标题字段名 | `title` |
| `description_field` | 描述字段名 | `description` 或 `summary` |
| `url_field` | 链接字段名 | `url` 或 `link` |
| `image_field` | 图片字段名 | `urlToImage` 或 `image` |
| `source_field` | 来源字段名 | `source.name` 或 `source` |
| `published_at_field` | 发布时间字段名 | `publishedAt` 或 `timestamp` |

## 📊 输出示例

生成的HTML报告包含：

- **头部区域**：标题、生成时间、统计信息
- **新闻卡片**：
  - 新闻图片
  - 国际/国内标签
  - 标题和描述
  - 详细内容（来自Web Search）
  - 来源和发布日期
  - 阅读全文链接
- **响应式设计**：自适应桌面和移动设备

## 🔍 Web Search集成

增强版本使用Claude的WebSearch工具来：

1. 搜索每条新闻标题
2. 获取详细内容
3. 在HTML报告中显示详细信息

**注意**：Web Search功能需要在Claude Code环境中运行。

## ⚙️ 高级配置

### 自定义输出样式

编辑 `enhanced_news_aggregator.py` 中的CSS部分：

```python
# 修改颜色主题
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);

# 修改卡片大小
grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));

# 修改字体
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
```

### 调整新闻数量

在 `fetch_headlines()` 方法中修改：

```python
for item in headlines[:10]:  # 改为你需要的数量
```

## 🐛 故障排除

### 问题：API返回401错误

**解决方案**：
- 检查API密钥是否正确
- 验证认证方式配置
- 确认API密钥未过期

### 问题：JSON解析错误

**解决方案**：
- 检查 `headlines_path` 是否正确
- 使用API文档验证响应格式
- 打印原始响应进行调试

### 问题：HTML报告为空

**解决方案**：
- 确认API返回了数据
- 检查字段名映射是否正确
- 验证API响应中是否包含必要字段

## 📝 在Claude Code中使用

1. 将skill文件夹放在项目的 `skills/` 目录下
2. Claude Code会自动发现并加载skill
3. 在对话中请求："生成全球新闻报告"

## 🔐 安全建议

- ✅ 不要在代码中硬编码API密钥
- ✅ 使用环境变量存储敏感信息
- ✅ 定期轮换API密钥
- ✅ 限制API调用频率

## 📚 支持的新闻API

### 国际新闻
- [NewsAPI](https://newsapi.org/)
- [The Guardian API](https://open-platform.theguardian.com/)
- [New York Times API](https://developer.nytimes.com/)
- [BBC News API](https://www.bbc.com/news)

### 国内新闻
- 新浪新闻API
- 腾讯新闻API
- 网易新闻API
- 头条新闻API

## 🤝 贡献

欢迎提交问题和改进建议！

## 📄 许可证

MIT License

## 📞 支持

如有问题，请参考：
- SKILL.md - Skill定义和使用说明
- api-config-example.json - 配置示例
- 各API官方文档
