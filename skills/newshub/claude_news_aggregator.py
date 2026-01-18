#!/usr/bin/env python3
"""
Claude-Integrated News Aggregator
Uses Claude's WebSearch tool to enrich news with detailed content
This script is designed to be called from Claude Code environment
"""

import json
import requests
from datetime import datetime
from typing import List, Dict, Any
import sys

class ClaudeIntegratedNewsAggregator:
    def __init__(self, config_path: str):
        """Initialize aggregator with config file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.all_news = []

    def fetch_headlines(self, api_config: Dict[str, Any], source_type: str) -> List[Dict]:
        """Fetch headlines from a single API"""
        try:
            headers = {}
            params = api_config.get('params', {}).copy()

            if api_config.get('auth_type') == 'bearer':
                headers['Authorization'] = f"Bearer {api_config.get('auth_header')}"
            elif api_config.get('auth_type') == 'api_key':
                params['apiKey'] = api_config.get('auth_header')

            print(f"📰 Fetching {source_type} news from {api_config.get('name', 'Unknown API')}...")
            response = requests.get(
                api_config.get('endpoint'),
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            # Navigate to headlines using path
            headlines_path = api_config.get('response_format', {}).get('headlines_path', 'articles')
            headlines = data
            for key in headlines_path.split('.'):
                headlines = headlines.get(key, [])

            # Extract relevant fields
            fmt = api_config.get('response_format', {})
            processed_news = []

            for item in headlines[:10]:  # Limit to 10
                news_item = {
                    'title': item.get(fmt.get('title_field', 'title'), 'N/A'),
                    'description': item.get(fmt.get('description_field', 'description'), ''),
                    'url': item.get(fmt.get('url_field', 'url'), ''),
                    'image': item.get(fmt.get('image_field', 'image'), ''),
                    'source': item.get(fmt.get('source_field', 'source'), source_type),
                    'published_at': item.get(fmt.get('published_at_field', 'publishedAt'), ''),
                    'source_type': source_type,
                    'detailed_content': ''
                }
                processed_news.append(news_item)

            print(f"✓ Successfully fetched {len(processed_news)} {source_type} headlines")
            return processed_news

        except Exception as e:
            print(f"✗ Error fetching {source_type} news: {str(e)}")
            return []

    def aggregate_news(self) -> List[Dict]:
        """Aggregate news from all configured APIs"""
        print("\n" + "="*60)
        print("🌍 Starting Global News Aggregation with Claude Integration")
        print("="*60 + "\n")

        # Fetch international news
        intl_news = self.fetch_headlines(
            self.config.get('international_api', {}),
            'International'
        )
        self.all_news.extend(intl_news)

        print()

        # Fetch domestic news
        domestic_news = self.fetch_headlines(
            self.config.get('domestic_api', {}),
            'Domestic'
        )
        self.all_news.extend(domestic_news)

        print(f"\n✓ Total news items aggregated: {len(self.all_news)}\n")
        return self.all_news

    def generate_html_report(self, output_path: str = None) -> str:
        """Generate HTML report from aggregated news"""
        if not output_path:
            output_path = self.config.get('output', {}).get('report_filename', 'global_news_report.html')

        report_title = self.config.get('output', {}).get('report_title', 'Global News Digest')

        html_content = self._generate_html_content(report_title)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✓ HTML report generated: {output_path}")
        return output_path

    def _generate_html_content(self, title: str) -> str:
        """Generate HTML content"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        news_cards = '\n'.join([
            self._generate_news_card(news, idx)
            for idx, news in enumerate(self.all_news, 1)
        ])

        intl_count = len([n for n in self.all_news if n['source_type'] == 'International'])
        domestic_count = len([n for n in self.all_news if n['source_type'] == 'Domestic'])

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
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
            margin-bottom: 10px;
            flex-grow: 1;
        }}

        .news-card-detailed {{
            color: #777;
            font-size: 0.9em;
            line-height: 1.5;
            padding: 10px;
            background: #f9f9f9;
            border-left: 3px solid #667eea;
            margin-bottom: 10px;
            border-radius: 3px;
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
            <h1>🌍 {title}</h1>
            <div class="timestamp">生成时间: {timestamp}</div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(self.all_news)}</div>
                    <div class="stat-label">总新闻数</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{intl_count}</div>
                    <div class="stat-label">国际新闻</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{domestic_count}</div>
                    <div class="stat-label">国内新闻</div>
                </div>
            </div>
        </div>

        <div class="news-grid">
            {news_cards}
        </div>

        <div class="footer">
            <p>© 2024 Global News Aggregator | 由Claude自动生成的新闻汇总报告</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _generate_news_card(self, news: Dict, index: int) -> str:
        """Generate a single news card HTML"""
        badge_class = 'badge-international' if news['source_type'] == 'International' else 'badge-domestic'
        badge_text = '🌐 国际' if news['source_type'] == 'International' else '🏠 国内'

        image_html = ''
        if news.get('image'):
            image_html = f'<img src="{news["image"]}" alt="{news["title"]}">'

        link_html = ''
        if news.get('url'):
            link_html = f'<a href="{news["url"]}" target="_blank" class="news-card-link">阅读全文 →</a>'

        detailed_html = ''
        if news.get('detailed_content'):
            detailed_html = f'<div class="news-card-detailed">{news["detailed_content"]}</div>'

        return f"""<div class="news-card">
            <div class="news-card-image">
                {image_html}
            </div>
            <div class="news-card-content">
                <span class="news-card-badge {badge_class}">{badge_text}</span>
                <h3 class="news-card-title">{news['title']}</h3>
                <p class="news-card-description">{news['description']}</p>
                {detailed_html}
                <div class="news-card-meta">
                    <span class="news-card-source">{news['source']}</span>
                    <span>{news['published_at'][:10] if news['published_at'] else '未知'}</span>
                </div>
                {link_html}
            </div>
        </div>"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python claude_news_aggregator.py <config_path> [output_path]")
        sys.exit(1)

    config_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        aggregator = ClaudeIntegratedNewsAggregator(config_path)
        aggregator.aggregate_news()
        aggregator.generate_html_report(output_path)
        print("\n✓ News aggregation completed successfully!")
        print("💡 Tip: Use Claude's WebSearch tool to enrich headlines with detailed content")
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
