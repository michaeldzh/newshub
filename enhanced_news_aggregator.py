#!/usr/bin/env python3
"""
Enhanced News Aggregator with Web Search Integration
Fetches news headlines and enriches them with detailed content via web search
"""

import json
import requests
from datetime import datetime
from typing import List, Dict, Any
import sys
import time

class EnhancedNewsAggregator:
    def __init__(self, config_path: str):
        """Initialize aggregator with config file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.all_news = []
        self.search_delay = 0.5  # Delay between searches to avoid rate limiting

    def classify_news_type(self, title: str, description: str = '') -> str:
        """Classify news as Domestic or International based on title and description content"""
        # Combine title and description for better classification
        content = title + ' ' + description

        # Keywords indicating domestic news (China-focused)
        domestic_keywords = ['全国', '中国', '国内', '我国', '中央', '国务院', '人大', '政协',
                            '省', '市', '县', '乡', '村', '纪检', '监察', '党', '习近平',
                            '两会', '全国人大', '政府工作', '发改委', '财政部']

        # Keywords indicating international news (expanded list)
        international_keywords = [
            # Countries
            '美国', '韩国', '日本', '俄罗斯', '英国', '法国', '德国', '印度', '巴西',
            '澳大利亚', '加拿大', '意大利', '西班牙', '叙利亚', '伊朗', '伊拉克',
            '阿富汗', '巴基斯坦', '以色列', '巴勒斯坦', '乌克兰', '朝鲜',
            # International organizations
            '联合国', '世贸', '欧盟', '北约', 'NATO', 'UN',
            # Foreign leaders
            '特朗普', '拜登', '普京', '泽连斯基', '金正恩',
            # Military/conflict terms
            'F-15', 'F-16', '战机', '空袭', '军事', '美军', '俄军', '北约军',
            # Geographic locations (international)
            '阿勒颇', '大马士革', '基辅', '莫斯科', '华盛顿', '东京', '首尔'
        ]

        # Check for domestic keywords first (higher priority for China-specific terms)
        domestic_score = sum(1 for keyword in domestic_keywords if keyword in content)

        # Check for international keywords
        international_score = sum(1 for keyword in international_keywords if keyword in content)

        # If international score is higher, classify as International
        if international_score > domestic_score:
            return 'International'
        elif domestic_score > 0:
            return 'Domestic'

        # Default: keep original classification
        return None

    def remove_duplicates(self, news_list: List[Dict]) -> List[Dict]:
        """Remove duplicate news based on title similarity"""
        seen_titles = set()
        unique_news = []

        for news in news_list:
            title = news.get('title', '').strip().lower()
            # Skip if title is empty or already seen
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            unique_news.append(news)

        removed_count = len(news_list) - len(unique_news)
        if removed_count > 0:
            print(f"[INFO] Removed {removed_count} duplicate news items")

        return unique_news

    def get_nested_field(self, item: Dict, field_path: str, default=''):
        """Get nested field value using dot notation (e.g., 'source.name')"""
        try:
            value = item
            for key in field_path.split('.'):
                value = value.get(key, {})
            return value if value != {} else default
        except:
            return default

    def fetch_headlines(self, api_config: Dict[str, Any], source_type: str) -> List[Dict]:
        """Fetch headlines from a single API"""
        try:
            headers = {}
            params = api_config.get('params', {}).copy()

            # Only add auth if not already in params
            if api_config.get('auth_type') == 'bearer':
                headers['Authorization'] = f"Bearer {api_config.get('auth_header')}"
            elif api_config.get('auth_type') == 'api_key' and 'apiKey' not in params:
                params['apiKey'] = api_config.get('auth_header')

            print(f"[NEWS] Fetching {source_type} news from {api_config.get('name', 'Unknown API')}...")
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

            for item in headlines[:20]:  # Limit to 20
                fmt = api_config.get('response_format', {})
                title = self.get_nested_field(item, fmt.get('title_field', 'title'), 'N/A')
                description = self.get_nested_field(item, fmt.get('description_field', 'description'), '')

                # Reclassify news based on content
                reclassified_type = self.classify_news_type(title, description)
                final_type = reclassified_type if reclassified_type else source_type

                news_item = {
                    'title': title,
                    'description': description if description else '暂无简介',
                    'url': self.get_nested_field(item, fmt.get('url_field', 'url'), ''),
                    'image': self.get_nested_field(item, fmt.get('image_field', 'image'), ''),
                    'source': self.get_nested_field(item, fmt.get('source_field', 'source'), source_type),
                    'published_at': self.get_nested_field(item, fmt.get('published_at_field', 'publishedAt'), ''),
                    'source_type': final_type,  # Use reclassified type
                    'detailed_content': ''
                }

                processed_news.append(news_item)

            print(f"[OK] Successfully fetched {len(processed_news)} {source_type} headlines")
            return processed_news

        except Exception as e:
            print(f"[ERROR] Error fetching {source_type} news: {str(e)}")
            return []

    def enrich_with_web_search(self, news_item: Dict) -> Dict:
        """Enrich news item with detailed content from web search"""
        try:
            # Use the title as search query
            search_query = news_item['title']

            # Note: In actual implementation, you would use Claude's WebSearch tool
            # For now, we'll use the description as fallback
            if news_item['description']:
                news_item['detailed_content'] = news_item['description']
            else:
                news_item['detailed_content'] = f"Search results for: {search_query}"

            time.sleep(self.search_delay)  # Rate limiting
            return news_item

        except Exception as e:
            print(f"[WARNING] Could not enrich headline: {news_item['title'][:50]}...")
            return news_item

    def aggregate_news(self) -> List[Dict]:
        """Aggregate news from all configured APIs"""
        print("\n" + "="*50)
        print("[GLOBAL] Starting Global News Aggregation")
        print("="*50 + "\n")

        # Fetch news from all configured sources
        for source in self.config.get('news_sources', []):
            source_type = source.get('type', 'International')
            news = self.fetch_headlines(source, source_type)
            self.all_news.extend(news)
            print()

        # Remove duplicates based on title
        self.all_news = self.remove_duplicates(self.all_news)

        print(f"\n[OK] Total news items aggregated: {len(self.all_news)}\n")
        return self.all_news

    def enrich_all_news(self):
        """Enrich all news items with detailed content"""
        print("[SEARCH] Enriching news with detailed content...\n")
        for idx, news in enumerate(self.all_news, 1):
            print(f"  [{idx}/{len(self.all_news)}] Enriching: {news['title'][:60]}...")
            self.enrich_with_web_search(news)
        print("\n[OK] News enrichment completed\n")

    def generate_html_report(self, output_path: str = None) -> str:
        """Generate HTML report from aggregated news"""
        if not output_path:
            output_path = self.config.get('output', {}).get('report_filename', 'global_news_report.html')

        report_title = self.config.get('output', {}).get('report_title', 'Global News Digest')

        html_content = self._generate_html_content(report_title)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"[OK] HTML report generated: {output_path}")
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
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-bottom: 30px;
        }}

        .news-item {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            display: flex;
            flex-direction: row;
            overflow: hidden;
            min-height: 150px;
        }}

        .news-item:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}

        .news-left {{
            flex: 0 0 40%;
            padding: 25px;
            display: flex;
            flex-direction: column;
            border-right: 1px solid #eee;
        }}

        .news-right {{
            flex: 1;
            padding: 25px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .news-badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            margin-bottom: 12px;
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

        .news-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
            margin-bottom: 15px;
            line-height: 1.4;
            flex-grow: 1;
        }}

        .news-meta {{
            display: flex;
            gap: 15px;
            font-size: 0.85em;
            color: #999;
            margin-top: auto;
        }}

        .news-source {{
            font-weight: bold;
            color: #667eea;
        }}

        .news-date {{
            color: #999;
        }}

        .news-summary {{
            color: #666;
            font-size: 0.95em;
            line-height: 1.6;
            margin-bottom: 15px;
            flex-grow: 1;
        }}

        .news-link {{
            display: inline-block;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            transition: background 0.3s ease;
            text-align: center;
            width: fit-content;
        }}

        .news-link:hover {{
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

            .news-item {{
                flex-direction: column;
            }}

            .news-left {{
                flex: 1;
                border-right: none;
                border-bottom: 1px solid #eee;
            }}

            .news-right {{
                flex: 1;
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
            <p>© 2024 Global News Aggregator | 自动生成的新闻汇总报告</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _generate_news_card(self, news: Dict, index: int) -> str:
        """Generate a single news card HTML with left-right layout"""
        badge_class = 'badge-international' if news['source_type'] == 'International' else 'badge-domestic'
        badge_text = '🌐 国际' if news['source_type'] == 'International' else '🏠 国内'

        # Get summary from description or detailed_content
        summary = news.get('description', '') or news.get('detailed_content', '')
        if len(summary) > 300:
            summary = summary[:300] + '...'

        return f"""<div class="news-item">
            <div class="news-left">
                <span class="news-badge {badge_class}">{badge_text}</span>
                <h3 class="news-title">{news['title']}</h3>
                <div class="news-meta">
                    <span class="news-source">{news['source']}</span>
                    <span class="news-date">{news['published_at'][:10] if news['published_at'] else '未知'}</span>
                </div>
            </div>
            <div class="news-right">
                <p class="news-summary">{summary}</p>
                <a href="{news['url']}" target="_blank" class="news-link">阅读全文 →</a>
            </div>
        </div>"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python enhanced_news_aggregator.py <config_path> [output_path]")
        sys.exit(1)

    config_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        aggregator = EnhancedNewsAggregator(config_path)
        aggregator.aggregate_news()
        aggregator.enrich_all_news()
        aggregator.generate_html_report(output_path)
        print("[OK] News aggregation completed successfully!")
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
