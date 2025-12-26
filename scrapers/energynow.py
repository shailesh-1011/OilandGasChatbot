"""
Energy Now Scraper
==================
Website: https://energynow.com/

Sections:
- https://energynow.com/category/us_news/
- https://energynow.com/category/international_news/
- https://energynow.com/category/press_releases/

Selectors:
- Date: <div class="post-date">December 19, 2025</div>
- Article links: URLs containing /YYYY/MM/ pattern
- Article Content: <p> tags

Logic:
1. Visit all section pages
2. Find articles with date class
3. Filter to today/yesterday only
4. Check if link already in CSV - skip if already scraped
5. Scrape article content
7. Save to CSV
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

SOURCE = 'energynow'
BASE_URL = 'https://energynow.com'
NEWS_URLS = [
    'https://energynow.com/category/us_news/',
    'https://energynow.com/category/us_news/page/2/',
    'https://energynow.com/category/us_news/page/3/',
    'https://energynow.com/category/us_news/page/4/',
    'https://energynow.com/category/us_news/page/5/',
    'https://energynow.com/category/international_news/',
    'https://energynow.com/category/international_news/page/2/',
    'https://energynow.com/category/international_news/page/3/',
    'https://energynow.com/category/press_releases/',
    'https://energynow.com/category/press_releases/page/2/',
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


def parse_date(date_text):
    """Parse date from text like 'December 19, 2025'"""
    try:
        return datetime.strptime(date_text.strip(), '%B %d, %Y').date()
    except:
        return None


def is_recent(date_text):
    """Check if date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def get_article_links(soup, url):
    """Extract article links from a section page - only for recent articles"""
    articles = []
    seen = set()
    
    # Find all date divs with class post-date
    date_divs = soup.find_all(class_='post-date')
    
    for date_div in date_divs:
        date_text = date_div.get_text().strip()
        
        # Find article link in parent container
        parent = date_div.parent.parent
        if not parent:
            continue
        
        # Find article links (URLs with /YYYY/ pattern)
        links = parent.find_all('a', href=True)
        article_link = None
        for a in links:
            href = a.get('href', '')
            if '/2025/' in href or '/2024/' in href:
                article_link = href
                break
        
        if not article_link:
            continue
        
        # Make absolute URL
        if not article_link.startswith('http'):
            article_link = BASE_URL + article_link
        
        # Skip duplicates
        if article_link in seen:
            continue
        seen.add(article_link)
        
        # Add all articles with dates
        if date_text:
            articles.append({
                'link': article_link,
                'date': date_text
            })
            print(f"  ✓ Found ({date_text}): {article_link[:55]}...")
        else:
            print(f"  ? No date found: {article_link[:55]}...")
    
    return articles


def get_article_content(url):
    """Scrape article content from article page"""
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get all paragraphs
        paragraphs = soup.find_all('p')
        
        # Filter out template text
        content_parts = []
        for p in paragraphs:
            text = p.get_text().strip()
            # Skip template/placeholder text
            if text and not text.startswith('{') and 'results_count' not in text:
                content_parts.append(text)
        
        content = '\n'.join(content_parts)
        return content
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ''


def save_articles(articles):
    """Save articles to CSV with clean formatting"""
    save_to_csv(articles, CSV_FILE, SOURCE)


def scrape(existing_links=None):
    """
    Main scrape function
    
    1. Fetch all section pages
    2. Filter by date (today/yesterday only)
    3. Skip already scraped links
    4. Scrape content & summarize
    5. Save to CSV
    """
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count energynow articles specifically
    en_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        en_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from Energy Now: {en_count} articles")
    
    all_recent_articles = []
    
    for news_url in NEWS_URLS:
        print(f"\n--- Checking {news_url} ---")
        
        try:
            response = requests.get(news_url, headers=headers, timeout=TIMEOUT)
            print(f"Status: {response.status_code}")
        except Exception as e:
            print(f"Error fetching {news_url}: {e}")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        recent_articles = get_article_links(soup, news_url)
        all_recent_articles.extend(recent_articles)
    
    # Remove duplicates across sections
    seen = set()
    unique_articles = []
    for article in all_recent_articles:
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
    print(f"Energy Now Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
