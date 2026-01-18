# Changelog

All notable changes to the Global News Aggregator Skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-17

### Added
- Initial release of Global News Aggregator Skill
- Support for dual-source news fetching (international + domestic)
- Three aggregator implementations:
  - `news_aggregator.py` - Basic version
  - `enhanced_news_aggregator.py` - Enhanced with web search support
  - `claude_news_aggregator.py` - Claude Code optimized version
- Professional HTML report generation with responsive design
- Flexible API configuration system supporting multiple auth types
- Interactive setup script (`setup.py`)
- Comprehensive test suite (`test_skill.py`)
- Demo script with sample data (`demo.py`)
- Complete documentation:
  - SKILL.md - Claude Code skill definition with execution instructions
  - README.md - Detailed usage documentation
  - USAGE.md - Claude Code usage guide
  - QUICKSTART.md - Quick start guide
  - PROJECT_SUMMARY.md - Project overview (Chinese)
- Configuration examples for popular news APIs
- MIT License

### Features
- Fetches 10 headlines from each configured news source
- Generates beautiful HTML reports with:
  - News cards with images
  - Source badges (International/Domestic)
  - Statistics summary
  - Responsive grid layout
  - Professional styling
- Supports multiple authentication methods (API key, Bearer token, none)
- Flexible JSON response parsing with configurable field mapping
- Error handling and logging
- Cross-platform support (Windows, Linux, macOS)

### Documentation
- English and Chinese documentation
- Step-by-step setup guide
- API configuration examples
- Troubleshooting guide
- Quick start guide

## [Unreleased]

### Planned Features
- Support for more than 2 news sources
- RSS feed support
- Email delivery of reports
- Scheduled report generation
- News filtering by category/keyword
- Multi-language support for reports
- Database storage for historical news
- API rate limiting and caching
- Custom report templates
- Export to PDF format
