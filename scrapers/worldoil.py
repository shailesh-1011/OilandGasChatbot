"""
World Oil News Scraper
Scrapes https://www.worldoil.com/news for oil & gas news articles
Filters for today and yesterday only, summarizes with BART model
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
import os
import re
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

# Configuration
SOURCE = 'worldoil'
NEWS_URLS = [
    'https://www.worldoil.com/news',
    'https://www.worldoil.com/news?page=2',
    'https://www.worldoil.com/news?page=3',
    'https://www.worldoil.com/news?page=4',
    'https://www.worldoil.com/news?page=5',
]
CSV_FILE = os.path.join(os.path.dirname(__file__), 'articles.csv')
TIMEOUT = 30  # seconds

# Date setup
today = datetime.now().date()
yesterday = today - timedelta(days=1)


def get_existing_links():
    """Get already scraped article links from CSV"""
    return get_links(CSV_FILE, SOURCE)


def parse_date(date_str):
    """Parse date string like 'December 19, 2025' to date object"""
    try:
        # Clean up the date string
        date_str = date_str.strip()
        return datetime.strptime(date_str, '%B %d, %Y').date()
    except ValueError:
        return None


def is_recent(article_date):
    """Check if date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def fetch_article_content(url):
    """Fetch full article text from article page"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"    Warning: Article returned status {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find the article content
        # World Oil uses article-body or similar classes
        content_selectors = [
            'div.article-body',
            'div.article-content',
            'div.content-body',
            'article',
            'div.entry-content',
            'div.post-content',
        ]
        
        content = None
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Get all paragraph text
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    content = ' '.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    if len(content) > 100:  # Reasonable content length
                        break
        
        # Fallback: get all paragraphs from main content area
        if not content or len(content) < 100:
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                paragraphs = main_content.find_all('p')
                content = ' '.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        
        if content and len(content) > 50:
            return content[:5000]  # Limit content length for summarization
        
        return None
        
    except Exception as e:
        print(f"    Error fetching article: {e}")
        return None


def scrape_news():
    """Main scraping function"""
    import time
    print("=" * 60)
    print(f"World Oil Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    existing_links = get_existing_links()
    print(f"Already scraped from World Oil: {len(existing_links)} articles")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    
    all_articles = []
    seen_urls = set()
    
    for news_url in NEWS_URLS:
        print(f"\n--- Checking {news_url} ---")
        try:
            response = requests.get(news_url, headers=headers, timeout=TIMEOUT)
            print(f"Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Failed to fetch page: {response.status_code}")
                continue
                
        except requests.RequestException as e:
            print(f"Request error: {e}")
            continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all links that match the news article pattern
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            
            # Match /news/YYYY/MM/DD/slug/ pattern
            match = re.search(r'/news/(\d{4})/(\d{2})/(\d{2})/([^/]+)', href)
            if not match:
                continue
                
            # Build full URL
            if href.startswith('/'):
                full_url = f"https://www.worldoil.com{href}"
            else:
                full_url = href
                
            # Skip duplicates
            if full_url in seen_urls or full_url in existing_links:
                continue
            seen_urls.add(full_url)
            
            # Extract date from URL
            year, month, day = match.groups()[:3]
            try:
                article_date = datetime(int(year), int(month), int(day)).date()
            except ValueError:
                continue
            
            # Get title from link text or parent
            title = link.get_text(strip=True)
            if not title or len(title) < 10:
                # Try to find title in parent or sibling
                parent = link.find_parent(['div', 'article', 'li'])
                if parent:
                    heading = parent.find(['h1', 'h2', 'h3', 'h4'])
                if heading:
                    title = heading.get_text(strip=True)
        
            if not title or len(title) < 10:
                continue
                
            # Add all articles
            print(f"  ✓ Found ({article_date.strftime('%B %d, %Y')}): {title[:50]}...")
            all_articles.append({
                'link': full_url,
                'title': title,
                'date': article_date.strftime('%Y-%m-%d')
            })
        
        time.sleep(1)  # Be nice to the server
    
    # Remove duplicates
    seen = set()
    articles_to_scrape = []
    for article in all_articles:
        if article['link'] not in seen:
            seen.add(article['link'])
            articles_to_scrape.append(article)
    
    print(f"\nFound {len(articles_to_scrape)} total articles")
    
    if not articles_to_scrape:
        print("No new articles to scrape")
        return 0
    
    # Filter out already scraped
    new_articles = [a for a in articles_to_scrape if a['link'] not in existing_links]
    print(f"New articles to scrape: {len(new_articles)}")
    
    if not new_articles:
        print("All articles already scraped")
        return 0
    
    # Fetch articles in parallel for speed
    results = fetch_articles_parallel(
        articles=new_articles,
        fetch_func=fetch_article_content,
        max_workers=10,
        source_name=SOURCE,
        standardize=True
    )
    
    # Save to CSV using shared utility
    if results:
        save_to_csv(results, CSV_FILE, SOURCE)
    
    return len(results)


if __name__ == '__main__':
    count = scrape_news()
    print(f"\nScraped {count} new articles")
