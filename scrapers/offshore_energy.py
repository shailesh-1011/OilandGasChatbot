"""
Offshore Energy Scraper
========================
Website: https://www.offshore-energy.biz/markets/oil-and-gas/

Selectors:
- Articles: <div data-teaser data-config="...">
- Date in data-config JSON: release_date: "2025-Dec-19"
- URL in data-config JSON: url
- Title in data-config JSON: title
- Article content: <p> paragraphs on article page

Logic:
1. Visit oil-and-gas category page
2. Extract articles from data-teaser divs
3. Parse release_date from data-config JSON
4. Filter to today/yesterday only
5. Visit article pages for full content
7. Save to CSV
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
import json
import html
from datetime import datetime, timedelta
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

SOURCE = 'offshore-energy'
BASE_URL = 'https://www.offshore-energy.biz'
NEWS_URLS = [
    'https://www.offshore-energy.biz/markets/oil-and-gas/',
    'https://www.offshore-energy.biz/markets/oil-and-gas/page/2/',
    'https://www.offshore-energy.biz/markets/oil-and-gas/page/3/',
    'https://www.offshore-energy.biz/markets/oil-and-gas/page/4/',
    'https://www.offshore-energy.biz/markets/oil-and-gas/page/5/',
]
CSV_FILE = os.path.join(os.path.dirname(__file__), 'articles.csv')
TIMEOUT = 30  # seconds

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
}


def get_existing_links():
    """Load existing article links to avoid duplicates"""
    return get_links(CSV_FILE, SOURCE)


def parse_date(date_str):
    """Parse date from format like '2025-Dec-19'"""
    try:
        return datetime.strptime(date_str, '%Y-%b-%d').date()
    except:
        return None


def is_recent(date_str):
    """Check if date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def format_date(date_str):
    """Format date to readable format"""
    parsed = parse_date(date_str)
    if parsed:
        return parsed.strftime('%B %d, %Y')
    return date_str


def get_article_links(soup):
    """Extract article links from data-teaser divs"""
    articles = []
    
    teasers = soup.find_all('div', attrs={'data-teaser': True})
    print(f"Found {len(teasers)} article teasers")
    
    for teaser in teasers:
        config_str = teaser.get('data-config', '{}')
        try:
            config = json.loads(config_str)
        except:
            continue
        
        url = config.get('url', '')
        title = config.get('title', '')
        release_date = config.get('release_date', '')
        
        # Decode HTML entities in title
        title = html.unescape(title)
        
        if not url or not release_date:
            continue
        
        if True:  # Collect all articles
            articles.append({
                'link': url,
                'date': format_date(release_date),
                'title': title
            })
            print(f"  ✓ Found ({release_date}): {title[:50]}...")
    
    return articles


def get_article_content(url):
    """Scrape article content from article page"""
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find paragraphs - skip the "Share this article" and promotional content
        paragraphs = soup.find_all('p')
        
        content_parts = []
        for p in paragraphs:
            text = p.get_text().strip()
            # Skip promotional/navigation content
            if any(skip in text.lower() for skip in [
                'share this article',
                'take the spotlight',
                'join us for a bigger',
                'subscribe to',
                'read more',
                'advertisement',
                'sponsored',
            ]):
                continue
            if len(text) > 50:  # Only meaningful paragraphs
                content_parts.append(text)
        
        return ' '.join(content_parts)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ''


def save_articles(articles):
    """Save articles to CSV with clean formatting"""
    save_to_csv(articles, CSV_FILE, SOURCE)


def scrape(existing_links=None):
    """
    Main scrape function
    
    1. Fetch multiple pages
    2. Skip already scraped links
    3. Scrape content
    4. Save to CSV
    """
    import time
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count offshore-energy articles specifically
    oe_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        oe_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from Offshore Energy: {oe_count} articles")
    
    all_articles = []
    
    for news_url in NEWS_URLS:
        print(f"\n--- Checking {news_url} ---")
        try:
            response = requests.get(news_url, headers=headers, timeout=TIMEOUT)
            print(f"Status: {response.status_code}")
        except Exception as e:
            print(f"Error fetching page: {e}")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = get_article_links(soup)
        all_articles.extend(articles)
        time.sleep(1)  # Be nice to the server
    
    # Remove duplicates
    seen = set()
    unique_articles = []
    for article in all_articles:
        if article['link'] not in seen:
            seen.add(article['link'])
            unique_articles.append(article)
    
    print(f"\nFound {len(unique_articles)} total articles")
    
    # Filter out already scraped
    new_articles = [a for a in unique_articles if a['link'] not in existing_links]
    print(f"New articles to scrape: {len(new_articles)}")
    
    if not new_articles:
        print("No new articles to scrape.")
        return []
    
    # Fetch articles in parallel for speed
    results = fetch_articles_parallel(
        articles=new_articles,
        fetch_func=get_article_content,
        max_workers=10,
        source_name=SOURCE,
        standardize=True
    )
    
    return results


# For standalone testing
if __name__ == "__main__":
    print("=" * 60)
    print(f"Offshore Energy Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    articles = scrape()
    print(f"\nScraped {len(articles)} new articles")
    
    if articles:
        save_articles(articles)
        print("\n--- Results ---")
        for a in articles:
            print(f"\nDate: {a['date']}")
            print(f"Link: {a['link']}")
            print(f"Content: {a['content'][:200]}..." if a['content'] else "No content")
