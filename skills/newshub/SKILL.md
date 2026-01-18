---
name: newshub
description: Automatically aggregate and summarize global news from international and domestic sources. Fetches the latest 10 trending headlines from each source, searches for detailed content, and generates a comprehensive HTML report with 20 global news stories. Use this skill when you need to create a curated news digest, monitor trending topics, or generate news reports combining international and domestic perspectives.
license: MIT
---

# Instructions for Claude Code

When this skill is invoked, follow these steps to generate a global news report:

## Step 1: Check for API Configuration

First, check if an `api-config.json` file exists in the skill directory:
- If it exists, proceed to Step 2
- If it doesn't exist, ask the user to provide their API configuration details:
  - International news API endpoint and authentication
  - Domestic news API endpoint and authentication
  - Then create the `api-config.json` file based on the template below

## Step 2: Verify Python Dependencies

Check if the required Python packages are installed:
- Run: `pip list | grep requests` to verify requests is installed
- If not installed, run: `pip install -r requirements.txt`

## Step 3: Execute the News Aggregator

Run the enhanced news aggregator script:
```bash
python enhanced_news_aggregator.py api-config.json
```

This will:
1. Fetch 10 headlines from the international news API
2. Fetch 10 headlines from the domestic news API
3. Generate an HTML report with all 20 news items

## Step 4: Enrich with Web Search (Optional)

If the user wants detailed content for each headline, use the WebSearch tool to:
1. Search for each headline title
2. Extract key information from search results
3. Add the detailed content to the news items

## Step 5: Present the Results

After the script completes:
1. Confirm the HTML report was generated successfully
2. Tell the user the location of the generated HTML file
3. Offer to open the file or provide a summary of the news items

## Error Handling

If errors occur:
- **API authentication errors**: Ask the user to verify their API credentials
- **Network errors**: Suggest checking internet connection and API endpoints
- **Missing dependencies**: Install required packages using pip
- **Invalid configuration**: Help the user fix the api-config.json file

## Configuration Template

If the user needs to create `api-config.json`, use this template:

```json
{
  "international_api": {
    "name": "NewsAPI",
    "endpoint": "https://newsapi.org/v2/top-headlines",
    "auth_type": "api_key",
    "auth_header": "YOUR_API_KEY_HERE",
    "params": {
      "country": "us",
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
    "endpoint": "YOUR_API_ENDPOINT",
    "auth_type": "bearer",
    "auth_header": "YOUR_TOKEN",
    "params": {
      "limit": 10
    },
    "response_format": {
      "headlines_path": "data.articles",
      "title_field": "title",
      "description_field": "description",
      "url_field": "url",
      "image_field": "image",
      "source_field": "source",
      "published_at_field": "publishedAt"
    }
  },
  "output": {
    "report_filename": "global_news_report.html",
    "report_title": "全球新闻汇总"
  }
}
```

---

# Global News Aggregator Skill

## Overview

This skill automatically aggregates global news from multiple sources and generates a comprehensive HTML report. It combines international and domestic news perspectives to provide a complete picture of trending topics.

## Capabilities

- **Dual-Source News Fetching**: Retrieves latest 10 headlines from international news API and 10 from domestic news API
- **Content Enrichment**: Uses web search to find detailed content for each headline
- **HTML Report Generation**: Creates a professional, formatted HTML report with all 20 news stories
- **Automatic Execution**: Runs end-to-end without manual intervention

## When to Use

Use this skill when you need to:
- Generate daily/weekly news digests
- Monitor trending topics across regions
- Create news reports combining global and local perspectives
- Aggregate news for analysis or distribution
- Build news dashboards or newsletters

## Prerequisites

Before using this skill, you need to:

1. **Configure API Credentials**: Set up your news API endpoints and authentication
2. **Provide API Documentation**: Share API details for both international and domestic news sources
3. **Specify Output Location**: Indicate where to save the generated HTML report

## How to Use

### Step 1: Prepare API Configuration

Create an `api-config.json` file with your API details:

```json
{
  "international_api": {
    "endpoint": "YOUR_INTERNATIONAL_API_ENDPOINT",
    "method": "GET",
    "auth_type": "bearer|api_key|none",
    "auth_header": "YOUR_AUTH_TOKEN_OR_KEY",
    "headlines_path": "data.articles",
    "title_field": "title",
    "description_field": "description",
    "url_field": "url",
    "limit": 10
  },
  "domestic_api": {
    "endpoint": "YOUR_DOMESTIC_API_ENDPOINT",
    "method": "GET",
    "auth_type": "bearer|api_key|none",
    "auth_header": "YOUR_AUTH_TOKEN_OR_KEY",
    "headlines_path": "data.articles",
    "title_field": "title",
    "description_field": "description",
    "url_field": "url",
    "limit": 10
  }
}
```

### Step 2: Run the Aggregator

Simply request: "Generate a global news report" or "Aggregate latest news headlines"

The skill will:
1. Fetch headlines from both APIs
2. Search for detailed content for each headline
3. Compile all information into a structured format
4. Generate a professional HTML report

### Step 3: Access the Report

The generated HTML report will include:
- News title and source
- Publication date
- Summary/description
- Key details from web search
- Professional styling and formatting

## Output Format

The skill generates an HTML file with:
- **Header**: Report title, generation timestamp
- **News Cards**: 20 news items with title, source, date, and summary
- **Styling**: Professional CSS with responsive design
- **Navigation**: Easy browsing and filtering options

## Limitations

- Requires valid API credentials for both news sources
- Web search results depend on search engine availability
- Rate limiting may apply to API calls
- HTML report size depends on content volume

## Configuration Examples

See `api-config-example.json` for detailed configuration templates for popular news APIs.

## Troubleshooting

**Issue**: API returns no headlines
- **Solution**: Verify API endpoint, authentication, and response format in config

**Issue**: Web search fails for some headlines
- **Solution**: Some headlines may not have searchable content; the skill will use API description as fallback

**Issue**: HTML report is incomplete
- **Solution**: Check API rate limits and ensure all credentials are valid

## Next Steps

1. Provide your API documentation or endpoints
2. I'll help configure the skill for your specific APIs
3. Test the aggregator with sample data
4. Deploy and schedule regular news reports
