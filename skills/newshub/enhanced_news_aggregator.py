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
import re
from urllib.parse import urlparse, urljoin
import html

class EnhancedNewsAggregator:
    def __init__(self, config_path: str):
        """Initialize aggregator with config file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.all_news = []
        self.search_delay = 0.5  # Delay between searches to avoid rate limiting

    def extract_news_source(self, title: str, description: str = '', fallback_source: str = '') -> str:
        """Extract original news source from title or description"""
        content = title + ' ' + description

        # Common patterns for news sources (ordered by priority)
        patterns = [
            r'【来源[：:]([^】]+)】',  # 【来源：xxx】
            r'来源[：:]\s*([^\s\)）]{2,15})',  # 来源：xxx
            r'（来源[：:]([^）]+)）',  # （来源：xxx）
            r'\(来源[：:]([^)]+)\)',  # (来源：xxx)
            r'据([^报道消息讯]{2,10})报道',  # 据xxx报道
            r'([^报道消息讯]{2,10})消息',  # xxx消息
            r'([^报道消息讯]{2,10})讯',  # xxx讯
            r'([^报道消息讯]{2,10})报道',  # xxx报道
            r'记者[^\s]{0,3}从([^获悉了解到]{2,10})',  # 记者从xxx获悉
            r'\(([^)]{2,8})\)$',  # Source in parentheses at end
            r'（([^）]{2,8})）$',  # Source in Chinese parentheses at end
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                source = match.group(1).strip()
                # Filter out common non-source words and aggregators
                excluded_words = ['记者', '编辑', '本报', '本网', '中华网', '新浪', '搜狐', '网易', '腾讯']
                if source and len(source) >= 2 and source not in excluded_words:
                    # Additional check: avoid generic terms
                    if not any(term in source for term in ['报道', '消息', '讯', '获悉', '了解']):
                        return source

        return fallback_source

    def classify_news_type(self, title: str, description: str = '') -> str:
        """Classify news into three categories: 国内, 国际, 科技"""
        content = title + ' ' + description

        # Tech keywords (highest priority)
        tech_keywords = [
            'AI', '人工智能', '机器学习', '深度学习', 'ChatGPT', 'GPT', '大模型',
            '芯片', '半导体', '5G', '6G', '量子', '区块链', '元宇宙',
            '科技', '技术', '互联网', '软件', '硬件', '算法', '数据',
            'iPhone', 'Android', '华为', '小米', 'OPPO', 'vivo',
            '特斯拉', '新能源', '电动车', '自动驾驶', '无人机',
            '航天', '卫星', '火箭', '探测器', '空间站'
        ]

        # Domestic keywords (comprehensive list)
        domestic_keywords = [
            # National level
            '全国', '中国', '国内', '我国', '中央', '国务院', '人大', '政协',
            '两会', '全国人大', '政府工作', '发改委', '财政部', '纪检', '监察', '党', '习近平',
            # Provinces (34)
            '北京', '上海', '天津', '重庆',
            '河北', '山西', '辽宁', '吉林', '黑龙江',
            '江苏', '浙江', '安徽', '福建', '江西', '山东',
            '河南', '湖北', '湖南', '广东', '海南',
            '四川', '贵州', '云南', '陕西', '甘肃', '青海',
            '内蒙古', '广西', '西藏', '宁夏', '新疆',
            '香港', '澳门', '台湾', '港澳台', '台海', '两岸',
            # Major cities
            '深圳', '广州', '成都', '杭州', '武汉', '西安', '郑州', '南京', '苏州',
            '长沙', '沈阳', '青岛', '济南', '哈尔滨', '长春', '合肥', '南昌', '福州',
            '厦门', '昆明', '兰州', '太原', '石家庄', '呼和浩特', '乌鲁木齐', '拉萨',
            '银川', '西宁', '南宁', '贵阳', '海口', '三亚', '洛阳', '包头',
            # Domestic enterprises
            '包钢', '宝钢', '鞍钢', '中石油', '中石化', '中海油', '国家电网', '南方电网',
            '中国移动', '中国联通', '中国电信', '华为', '小米', '阿里', '腾讯', '百度',
            '京东', '美团', '滴滴', '比亚迪', '吉利', '长城汽车', '蔚来', '理想',
            # Domestic affairs
            '省', '市', '县', '乡', '村', '民生', '就业', '医保', '养老', '教育', '房价',
            '成品油', '油价', '景区', '旅游', '春运', '高铁', '地铁'
        ]

        # International keywords
        international_keywords = [
            '欧洲', '美洲', '非洲', '大洋洲', '中东', '东南亚', '南亚', '拉美',
            '美国', '韩国', '日本', '俄罗斯', '英国', '法国', '德国', '印度',
            '八国', '七国', 'G7', 'G20', '联合国', '北约', '欧盟',
            '特朗普', '拜登', '普京', '泽连斯基', '金正恩',
            '战机', '空袭', '军事', '美军', '俄军', '关税', '贸易战', '制裁'
        ]

        # Calculate scores
        tech_score = sum(1 for keyword in tech_keywords if keyword in content)
        domestic_score = sum(1 for keyword in domestic_keywords if keyword in content)
        international_score = sum(1 for keyword in international_keywords if keyword in content)

        # Classify based on highest score (prioritize domestic over international)
        if tech_score > 0:
            return '科技'
        elif domestic_score > 0 and domestic_score >= international_score:
            return '国内'
        elif international_score > 0:
            return '国际'

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

                # Extract original news source from content
                api_source = self.get_nested_field(item, fmt.get('source_field', 'source'), source_type)
                final_source = self.extract_news_source(title, description, api_source)

                news_item = {
                    'title': title,
                    'description': description if description else '暂无简介',
                    'url': self.get_nested_field(item, fmt.get('url_field', 'url'), ''),
                    'image': self.get_nested_field(item, fmt.get('image_field', 'image'), ''),
                    'source': final_source,
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

    def extract_content_from_url(self, url: str) -> tuple:
        """Extract description, image, and source from news URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Handle encoding properly
            response.encoding = response.apparent_encoding
            html_content = response.text

            # Extract meta description
            description = ''
            desc_match = re.search(r'<meta\s+(?:name|property)=["\'](?:description|og:description)["\']?\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if desc_match:
                description = html.unescape(desc_match.group(1))

            # Extract og:image
            image = ''
            img_match = re.search(r'<meta\s+property=["\']og:image["\']?\s+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if img_match:
                image_url = img_match.group(1)
                # Convert relative URL to absolute URL
                image = urljoin(url, image_url)

            # Extract source from page (common patterns)
            source = ''
            source_patterns = [
                r'来源[：:]\s*([^\s<>]{2,10})',
                r'<span[^>]*class=["\'][^"\']*source[^"\']*["\'][^>]*>([^<]{2,10})</span>',
                r'<div[^>]*class=["\'][^"\']*source[^"\']*["\'][^>]*>([^<]{2,10})</div>',
            ]
            for pattern in source_patterns:
                src_match = re.search(pattern, html_content, re.IGNORECASE)
                if src_match:
                    source = html.unescape(src_match.group(1).strip())
                    if source and len(source) >= 2:
                        break

            return description, image, source

        except Exception as e:
            return '', '', ''

    def is_incomplete_summary(self, text: str) -> bool:
        """Check if summary appears to be incomplete"""
        if not text or text == '暂无简介':
            return True

        text = text.strip()

        # Check if ends with ellipsis or incomplete patterns
        if text.endswith('...') or text.endswith('..'):
            return True

        # Check if too short (less than 50 chars)
        if len(text) < 50:
            return True

        # Check if ends with incomplete sentence (ends with digit followed by ellipsis pattern)
        if len(text) > 2 and text[-2:].isdigit():
            return True

        return False

    def enrich_with_web_search(self, news_item: Dict) -> Dict:
        """Enrich news item with detailed content from web page"""
        try:
            # Fetch description if missing or incomplete
            should_fetch = (
                not news_item['description'] or
                news_item['description'] == '暂无简介' or
                self.is_incomplete_summary(news_item['description'])
            )

            if should_fetch and news_item['url']:
                desc, _, web_source = self.extract_content_from_url(news_item['url'])

                if desc and len(desc) > len(news_item.get('description', '')):
                    news_item['description'] = desc
                    news_item['detailed_content'] = desc

                # Update source if found on web page
                if web_source:
                    news_item['source'] = web_source

            time.sleep(self.search_delay)  # Rate limiting
            return news_item

        except Exception as e:
            print(f"[WARNING] Could not enrich: {news_item['title'][:50]}...")
            return news_item

    def balance_news_count(self, news_list: List[Dict]) -> List[Dict]:
        """Balance news count: 10 domestic, 10 international, 5 tech"""
        domestic_news = [n for n in news_list if n['source_type'] == '国内']
        international_news = [n for n in news_list if n['source_type'] == '国际']
        tech_news = [n for n in news_list if n['source_type'] == '科技']

        print(f"[INFO] Before balancing: {len(domestic_news)} 国内, {len(international_news)} 国际, {len(tech_news)} 科技")

        # Take specified number from each type
        balanced_news = []
        balanced_news.extend(domestic_news[:10])
        balanced_news.extend(international_news[:10])
        balanced_news.extend(tech_news[:5])

        print(f"[INFO] After balancing: {len([n for n in balanced_news if n['source_type'] == '国内'])} 国内, {len([n for n in balanced_news if n['source_type'] == '国际'])} 国际, {len([n for n in balanced_news if n['source_type'] == '科技'])} 科技")

        return balanced_news

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

        # Balance news count to ensure proper distribution
        self.all_news = self.balance_news_count(self.all_news)

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

        # Group news by category
        domestic_news = [n for n in self.all_news if n['source_type'] == '国内']
        intl_news = [n for n in self.all_news if n['source_type'] == '国际']
        tech_news = [n for n in self.all_news if n['source_type'] == '科技']

        # Generate news cards for each category with separate numbering
        domestic_cards = '\n'.join([
            self._generate_news_card(news, idx)
            for idx, news in enumerate(domestic_news, 1)
        ])

        intl_cards = '\n'.join([
            self._generate_news_card(news, idx)
            for idx, news in enumerate(intl_news, 1)
        ])

        tech_cards = '\n'.join([
            self._generate_news_card(news, idx)
            for idx, news in enumerate(tech_news, 1)
        ])

        # Combine into categorized sections
        news_cards = f"""
            <div class="category-section">
                <h2 class="category-title">🏠 国内新闻</h2>
                <div class="news-grid">
                    {domestic_cards}
                </div>
            </div>

            <div class="category-section">
                <h2 class="category-title">🌐 国际新闻</h2>
                <div class="news-grid">
                    {intl_cards}
                </div>
            </div>

            <div class="category-section">
                <h2 class="category-title">💻 科技新闻</h2>
                <div class="news-grid">
                    {tech_cards}
                </div>
            </div>
        """

        domestic_count = len(domestic_news)
        intl_count = len(intl_news)
        tech_count = len(tech_news)

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

        .category-section {{
            margin-bottom: 40px;
        }}

        .category-title {{
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            color: #333;
            font-size: 1.8em;
            font-weight: bold;
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
            padding: 25px;
            overflow: hidden;
        }}

        .news-item:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
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

        .badge-tech {{
            background: #e8f5e9;
            color: #388e3c;
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

        .news-image {{
            width: 100%;
            max-height: 250px;
            object-fit: contain;
            border-radius: 8px;
            margin-bottom: 15px;
            background: #f5f5f5;
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
                    <div class="stat-number">{domestic_count}</div>
                    <div class="stat-label">国内新闻</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{intl_count}</div>
                    <div class="stat-label">国际新闻</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{tech_count}</div>
                    <div class="stat-label">科技新闻</div>
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

    def add_punctuation_to_summary(self, text: str) -> str:
        """Add punctuation to summary text that lacks proper punctuation"""
        if not text or text == '暂无简介':
            return text

        text = text.strip()
        result = []
        last_punct_pos = 0

        for i, char in enumerate(text):
            result.append(char)

            # Check if current char is punctuation
            if char in '。！？；，.!?;,':
                last_punct_pos = i
            else:
                # If no punctuation for 50+ chars, add comma after certain words
                if i - last_punct_pos > 50:
                    # Add comma after common sentence-ending particles
                    if char in '的了着过' and i < len(text) - 1:
                        result.append('，')
                        last_punct_pos = i
                    # Add period before numbered items (01, 02, etc.)
                    elif i < len(text) - 2 and text[i:i+2].isdigit():
                        if result[-1] not in '。！？；，.!?;,':
                            result.insert(-1, '。')
                            last_punct_pos = i

        text = ''.join(result)

        # Ensure ends with proper punctuation
        if text and text[-1] not in '。！？；，.!?;,':
            text += '。'

        return text

    def _generate_news_card(self, news: Dict, index: int) -> str:
        """Generate a single news card HTML with vertical layout"""
        badge_class = 'badge-international' if news['source_type'] == '国际' else ('badge-tech' if news['source_type'] == '科技' else 'badge-domestic')
        badge_text = '🌐 国际' if news['source_type'] == '国际' else ('💻 科技' if news['source_type'] == '科技' else '🏠 国内')

        # Get summary from description or detailed_content (no truncation)
        summary = news.get('description', '') or news.get('detailed_content', '') or '暂无简介'

        # Add punctuation to summary
        summary = self.add_punctuation_to_summary(summary)

        # Generate image HTML if available
        image_html = ''
        if news.get('image'):
            image_html = f'<img src="{news["image"]}" alt="新闻配图" class="news-image" onerror="this.style.display=\'none\'">'

        return f"""<div class="news-item">
            <span class="news-badge {badge_class}">{badge_text}</span>
            <h3 class="news-title">{index}、{news['title']}</h3>
            {image_html}
            <p class="news-summary">{summary}</p>
            <div class="news-meta">
                <span class="news-source">来源：{news['source']}</span>
                <span class="news-date">{news['published_at'][:10] if news['published_at'] else '未知'}</span>
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
