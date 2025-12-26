"""
BOE Report Scraper
==================
Website: https://boereport.com/

Selectors:
- Article links: URLs containing /YYYY/MM/DD/ pattern
- Date: Extracted from URL (e.g., /2025/12/19/)
- Article Content: <p> tags

Logic:
1. Visit main page
2. Extract article links with date in URL
3. Filter to today/yesterday only
4. Check if link already in CSV - skip if already scraped
5. Scrape article content
7. Save to CSV
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

SOURCE = 'boereport'
BASE_URL = 'https://boereport.com'
NEWS_URLS = [
    'https://boereport.com/',
    'https://boereport.com/page/2/',
    'https://boereport.com/page/3/',
    'https://boereport.com/page/4/',
    'https://boereport.com/page/5/',
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


def extract_date_from_url(url):
    """Extract date from URL like /2025/12/19/"""
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).date()
        except:
            pass
    return None


def format_date(date_obj):
    """Format date as standardized YYYY-MM-DD"""
    return standardize_date(date_obj)


def is_recent(url):
    """Check if URL date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def get_article_links(soup):
    """Extract article links from the main page - only for recent articles"""
    articles = []
    seen = set()
    
    # Find all links with date pattern in URL
    all_links = soup.find_all('a', href=True)
    
    for a_tag in all_links:
        link = a_tag['href']
        
        # Skip if not an article link (must have /YYYY/MM/DD/ pattern)
        if not re.search(r'/\d{4}/\d{2}/\d{2}/', link):
            continue
        
        # Make absolute URL
        if not link.startswith('http'):
            link = BASE_URL + link
        
        # Skip duplicates
        if link in seen:
            continue
        seen.add(link)
        
        # Add all articles
        date_obj = extract_date_from_url(link)
        date_str = format_date(date_obj) if date_obj else 'Unknown'
        articles.append({
            'link': link,
            'date': date_str
        })
        print(f"  ✓ Found ({date_str}): {link[:60]}...")
    
    return articles


def get_article_content(url):
    """Scrape article content from article page"""
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get all paragraphs
        paragraphs = soup.find_all('p')
        content = '\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
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
    
    1. Fetch multiple pages
    2. Skip already scraped links
    3. Scrape content
    4. Save to CSV
    """
    import time
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count boereport articles specifically
    boe_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        boe_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from BOE Report: {boe_count} articles")
    
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
    print(f"BOE Report Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
