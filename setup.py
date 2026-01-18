#!/usr/bin/env python3
"""
Setup script for Global News Aggregator Skill
Helps users configure and test the skill before using it with Claude Code
"""

import json
import os
import sys
import subprocess

def check_dependencies():
    """Check if required Python packages are installed"""
    print("🔍 Checking dependencies...")
    try:
        import requests
        print("✓ requests package is installed")
        return True
    except ImportError:
        print("✗ requests package is not installed")
        return False

def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("✗ Failed to install dependencies")
        return False

def create_config_file():
    """Interactive configuration file creation"""
    print("\n⚙️  Let's create your API configuration file")
    print("=" * 60)

    config = {
        "international_api": {},
        "domestic_api": {},
        "output": {}
    }

    # International API configuration
    print("\n📰 International News API Configuration")
    print("-" * 60)

    use_newsapi = input("Use NewsAPI.org? (y/n) [y]: ").strip().lower() or 'y'

    if use_newsapi == 'y':
        api_key = input("Enter your NewsAPI.org API key: ").strip()
        country = input("Enter country code (us/gb/ca/au) [us]: ").strip() or 'us'

        config["international_api"] = {
            "name": "NewsAPI",
            "endpoint": "https://newsapi.org/v2/top-headlines",
            "auth_type": "api_key",
            "auth_header": api_key,
            "params": {
                "country": country,
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
        }
    else:
        print("Please configure your custom international news API:")
        config["international_api"] = {
            "name": input("API name: ").strip(),
            "endpoint": input("API endpoint URL: ").strip(),
            "auth_type": input("Auth type (api_key/bearer/none): ").strip(),
            "auth_header": input("API key or token: ").strip(),
            "params": {"limit": 10},
            "response_format": {
                "headlines_path": input("Path to headlines array (e.g., 'articles' or 'data.items'): ").strip(),
                "title_field": "title",
                "description_field": "description",
                "url_field": "url",
                "image_field": "image",
                "source_field": "source",
                "published_at_field": "publishedAt"
            }
        }

    # Domestic API configuration
    print("\n🏠 Domestic News API Configuration")
    print("-" * 60)

    has_domestic = input("Do you have a domestic news API? (y/n) [y]: ").strip().lower() or 'y'

    if has_domestic == 'y':
        print("Please configure your domestic news API:")
        config["domestic_api"] = {
            "name": input("API name: ").strip(),
            "endpoint": input("API endpoint URL: ").strip(),
            "auth_type": input("Auth type (api_key/bearer/none): ").strip(),
            "auth_header": input("API key or token: ").strip(),
            "params": {"limit": 10},
            "response_format": {
                "headlines_path": input("Path to headlines array: ").strip(),
                "title_field": "title",
                "description_field": "description",
                "url_field": "url",
                "image_field": "image",
                "source_field": "source",
                "published_at_field": "publishedAt"
            }
        }
    else:
        # Use same API for both
        print("Using international API for domestic news as well...")
        config["domestic_api"] = config["international_api"].copy()

    # Output configuration
    print("\n📄 Output Configuration")
    print("-" * 60)
    filename = input("Output filename [global_news_report.html]: ").strip() or "global_news_report.html"
    title = input("Report title [全球新闻汇总]: ").strip() or "全球新闻汇总"

    config["output"] = {
        "report_filename": filename,
        "report_title": title
    }

    # Save configuration
    config_path = "api-config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Configuration saved to {config_path}")
    return config_path

def test_configuration(config_path):
    """Test the configuration by running the aggregator"""
    print("\n🧪 Testing configuration...")
    print("=" * 60)

    test = input("Run a test to fetch news? (y/n) [y]: ").strip().lower() or 'y'

    if test == 'y':
        try:
            print("\nRunning news aggregator...")
            result = subprocess.run(
                [sys.executable, "enhanced_news_aggregator.py", config_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("✓ Test successful!")
                print("\nOutput:")
                print(result.stdout)
                return True
            else:
                print("✗ Test failed!")
                print("\nError:")
                print(result.stderr)
                return False
        except subprocess.TimeoutExpired:
            print("✗ Test timed out (took more than 30 seconds)")
            return False
        except Exception as e:
            print(f"✗ Test failed with error: {str(e)}")
            return False

    return True

def main():
    """Main setup workflow"""
    print("=" * 60)
    print("🌍 Global News Aggregator Skill - Setup")
    print("=" * 60)

    # Check dependencies
    if not check_dependencies():
        install = input("\nInstall dependencies now? (y/n) [y]: ").strip().lower() or 'y'
        if install == 'y':
            if not install_dependencies():
                print("\n❌ Setup failed: Could not install dependencies")
                return 1
        else:
            print("\n⚠️  Please install dependencies manually: pip install -r requirements.txt")
            return 1

    # Check for existing config
    if os.path.exists("api-config.json"):
        print("\n⚠️  Found existing api-config.json")
        overwrite = input("Create new configuration? (y/n) [n]: ").strip().lower() or 'n'
        if overwrite != 'y':
            config_path = "api-config.json"
            print(f"Using existing configuration: {config_path}")
        else:
            config_path = create_config_file()
    else:
        config_path = create_config_file()

    # Test configuration
    test_configuration(config_path)

    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review your configuration in api-config.json")
    print("2. Run the aggregator: python enhanced_news_aggregator.py api-config.json")
    print("3. Use in Claude Code by saying: 'Generate a global news report'")
    print("\nFor more information, see README.md")

    return 0

if __name__ == '__main__':
    sys.exit(main())
