#!/usr/bin/env python3
"""
Demo script to test the news aggregator with sample data
This helps verify the skill works before connecting real APIs
"""

import json
from datetime import datetime, timedelta
from enhanced_news_aggregator import EnhancedNewsAggregator

def create_demo_config():
    """Create a demo configuration with sample data"""
    demo_config = {
        "international_api": {
            "name": "Demo International News",
            "endpoint": "https://newsapi.org/v2/top-headlines",
            "method": "GET",
            "auth_type": "api_key",
            "auth_header": "demo_key",
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
            "name": "Demo Domestic News",
            "endpoint": "https://api.example.com/news",
            "method": "GET",
            "auth_type": "bearer",
            "auth_header": "demo_token",
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
            "report_filename": "demo_news_report.html",
            "report_title": "全球新闻汇总 - 演示版",
            "include_images": True,
            "include_timestamps": True
        }
    }

    with open('demo-config.json', 'w', encoding='utf-8') as f:
        json.dump(demo_config, f, indent=2, ensure_ascii=False)

    print("✓ Demo configuration created: demo-config.json")

def create_sample_news_data():
    """Create sample news data for testing"""
    sample_news = [
        {
            "title": "AI技术取得重大突破",
            "description": "新型人工智能模型在多项基准测试中创造新纪录",
            "url": "https://example.com/ai-breakthrough",
            "urlToImage": "https://via.placeholder.com/400x300?text=AI+Breakthrough",
            "source": {"name": "Tech News Daily"},
            "publishedAt": (datetime.now() - timedelta(hours=2)).isoformat()
        },
        {
            "title": "全球气候峰会达成新协议",
            "description": "各国领导人就碳排放目标达成共识",
            "url": "https://example.com/climate-summit",
            "urlToImage": "https://via.placeholder.com/400x300?text=Climate+Summit",
            "source": {"name": "Global News Network"},
            "publishedAt": (datetime.now() - timedelta(hours=4)).isoformat()
        },
        {
            "title": "科技巨头发布新产品线",
            "description": "创新产品将改变用户体验",
            "url": "https://example.com/new-products",
            "urlToImage": "https://via.placeholder.com/400x300?text=New+Products",
            "source": {"name": "Innovation Weekly"},
            "publishedAt": (datetime.now() - timedelta(hours=6)).isoformat()
        },
        {
            "title": "医学研究发现新治疗方法",
            "description": "科学家开发出针对常见疾病的新疗法",
            "url": "https://example.com/medical-breakthrough",
            "urlToImage": "https://via.placeholder.com/400x300?text=Medical+Breakthrough",
            "source": {"name": "Science Today"},
            "publishedAt": (datetime.now() - timedelta(hours=8)).isoformat()
        },
        {
            "title": "太空探索取得新进展",
            "description": "火星任务成功完成关键阶段",
            "url": "https://example.com/space-mission",
            "urlToImage": "https://via.placeholder.com/400x300?text=Space+Mission",
            "source": {"name": "Space News"},
            "publishedAt": (datetime.now() - timedelta(hours=10)).isoformat()
        },
        {
            "title": "经济数据显示增长势头",
            "description": "第四季度GDP增长超预期",
            "url": "https://example.com/economy",
            "urlToImage": "https://via.placeholder.com/400x300?text=Economy",
            "source": {"name": "Financial Times"},
            "publishedAt": (datetime.now() - timedelta(hours=12)).isoformat()
        },
        {
            "title": "体育界传来重大新闻",
            "description": "运动员创造新的世界纪录",
            "url": "https://example.com/sports",
            "urlToImage": "https://via.placeholder.com/400x300?text=Sports",
            "source": {"name": "Sports Central"},
            "publishedAt": (datetime.now() - timedelta(hours=14)).isoformat()
        },
        {
            "title": "文化活动吸引全球关注",
            "description": "国际艺术节展示多元文化",
            "url": "https://example.com/culture",
            "urlToImage": "https://via.placeholder.com/400x300?text=Culture",
            "source": {"name": "Culture Magazine"},
            "publishedAt": (datetime.now() - timedelta(hours=16)).isoformat()
        },
        {
            "title": "教育改革推动创新学习",
            "description": "新教学方法提高学生成绩",
            "url": "https://example.com/education",
            "urlToImage": "https://via.placeholder.com/400x300?text=Education",
            "source": {"name": "Education Weekly"},
            "publishedAt": (datetime.now() - timedelta(hours=18)).isoformat()
        },
        {
            "title": "环保倡议获得广泛支持",
            "description": "全球企业承诺减少碳足迹",
            "url": "https://example.com/environment",
            "urlToImage": "https://via.placeholder.com/400x300?text=Environment",
            "source": {"name": "Green News"},
            "publishedAt": (datetime.now() - timedelta(hours=20)).isoformat()
        }
    ]

    return sample_news

def create_demo_html_report():
    """Create a demo HTML report with sample data"""
    sample_intl_news = create_sample_news_data()
    sample_domestic_news = create_sample_news_data()

    # Modify domestic news titles
    for i, news in enumerate(sample_domestic_news):
        news['title'] = f"[国内] {news['title']}"
        news['source']['name'] = f"国内{news['source']['name']}"

    all_news = sample_intl_news + sample_domestic_news

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    news_cards = '\n'.join([
        f"""<div class="news-card">
            <div class="news-card-image">
                <img src="{news['urlToImage']}" alt="{news['title']}">
            </div>
            <div class="news-card-content">
                <span class="news-card-badge {'badge-domestic' if '[国内]' in news['title'] else 'badge-international'}">
                    {'🏠 国内' if '[国内]' in news['title'] else '🌐 国际'}
                </span>
                <h3 class="news-card-title">{news['title']}</h3>
                <p class="news-card-description">{news['description']}</p>
                <div class="news-card-meta">
                    <span class="news-card-source">{news['source']['name']}</span>
                    <span>{news['publishedAt'][:10]}</span>
                </div>
                <a href="{news['url']}" target="_blank" class="news-card-link">阅读全文 →</a>
            </div>
        </div>"""
        for news in all_news
    ])

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>全球新闻汇总 - 演示版</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            background: white;
            padding: 40px 30px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            text-align: center;
        }}

        .header h1 {{
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .timestamp {{
            color: #666;
            font-size: 0.95em;
        }}

        .header .stats {{
            margin-top: 15px;
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
        }}

        .stat {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}

        .stat-number {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}

        .stat-label {{
            color: #999;
            font-size: 0.9em;
            margin-top: 5px;
        }}

        .news-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .news-card {{
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            display: flex;
            flex-direction: column;
        }}

        .news-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.2);
        }}

        .news-card-image {{
            width: 100%;
            height: 200px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            overflow: hidden;
        }}

        .news-card-image img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .news-card-content {{
            padding: 20px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }}

        .news-card-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            margin-bottom: 10px;
            width: fit-content;
        }}

        .badge-international {{
            background: #e3f2fd;
            color: #1976d2;
        }}

        .badge-domestic {{
            background: #f3e5f5;
            color: #7b1fa2;
        }}

        .news-card-title {{
            font-size: 1.1em;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
            line-height: 1.4;
        }}

        .news-card-description {{
            color: #666;
            font-size: 0.95em;
            line-height: 1.5;
            margin-bottom: 15px;
            flex-grow: 1;
        }}

        .news-card-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 15px;
            border-top: 1px solid #eee;
            font-size: 0.85em;
            color: #999;
        }}

        .news-card-source {{
            font-weight: bold;
            color: #667eea;
        }}

        .news-card-link {{
            display: inline-block;
            margin-top: 10px;
            padding: 8px 15px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            transition: background 0.3s ease;
        }}

        .news-card-link:hover {{
            background: #764ba2;
        }}

        .footer {{
            text-align: center;
            color: white;
            padding: 20px;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}

            .news-grid {{
                grid-template-columns: 1fr;
            }}

            .header .stats {{
                flex-direction: column;
                gap: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌍 全球新闻汇总 - 演示版</h1>
            <div class="timestamp">生成时间: {timestamp}</div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(all_news)}</div>
                    <div class="stat-label">总新闻数</div>
                </div>
                <div class="stat">
                    <div class="stat-number">10</div>
                    <div class="stat-label">国际新闻</div>
                </div>
                <div class="stat">
                    <div class="stat-number">10</div>
                    <div class="stat-label">国内新闻</div>
                </div>
            </div>
        </div>

        <div class="news-grid">
            {news_cards}
        </div>

        <div class="footer">
            <p>© 2024 Global News Aggregator | 演示版本 - 由Claude自动生成的新闻汇总报告</p>
        </div>
    </div>
</body>
</html>"""

    with open('demo_news_report.html', 'w', encoding='utf-8') as f:
        f.write(html)

    print("✓ Demo HTML report created: demo_news_report.html")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🌍 Global News Aggregator - Demo Setup")
    print("="*60 + "\n")

    create_demo_config()
    create_demo_html_report()

    print("\n✓ Demo setup completed!")
    print("\n📋 Next steps:")
    print("  1. Open demo_news_report.html in your browser to see the output format")
    print("  2. Update api-config.json with your real API credentials")
    print("  3. Run: python enhanced_news_aggregator.py api-config.json")
    print("\n")
