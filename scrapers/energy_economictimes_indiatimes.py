"""
ET Energy World Scraper
========================
Website: https://energy.economictimes.indiatimes.com/news/oil-and-gas

Selectors:
- Article links: /news/oil-and-gas/TITLE/ARTICLE_ID
- Date: Found on article page - "Published On Dec 20, 2025 at 10:38 AM IST"
- Article Content: <div class="article-section__body__news">

Logic:
1. Visit listing page
2. Get all article links
3. Visit each article to get date
4. Filter to today/yesterday only
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

SOURCE = 'economictimes'
BASE_URL = 'https://energy.economictimes.indiatimes.com'
NEWS_URLS = [
    'https://energy.economictimes.indiatimes.com/news/oil-and-gas',
    'https://energy.economictimes.indiatimes.com/news/oil-and-gas/2',
    'https://energy.economictimes.indiatimes.com/news/oil-and-gas/3',
    'https://energy.economictimes.indiatimes.com/news/oil-and-gas/4',
    'https://energy.economictimes.indiatimes.com/news/oil-and-gas/5',
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
    """Parse date from text like 'Published On Dec 20, 2025 at 10:38 AM IST'"""
    try:
        # Extract just the date part
        match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})', date_text)
        if match:
            month, day, year = match.groups()
            date_str = f"{month} {day}, {year}"
            return datetime.strptime(date_str, '%b %d, %Y').date()
    except:
        pass
    return None


def is_recent(date_obj):
    """Check if date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def get_article_links(soup):
    """Extract article links from the listing page"""
    links = soup.find_all('a', href=True)
    article_links = []
    seen = set()
    
    for a in links:
        href = a.get('href', '')
        
        # Only article links with the pattern /news/oil-and-gas/TITLE/ID
        if '/news/oil-and-gas/' not in href:
            continue
        if len(href) < 60:
            continue
        
        # Clean URL - remove query params
        clean_url = href.split('?')[0]
        
        # Make absolute URL
        if clean_url.startswith('/'):
            clean_url = BASE_URL + clean_url
        
        if clean_url in seen:
            continue
        seen.add(clean_url)
        
        article_links.append(clean_url)
    
    return article_links


def get_article_date_and_content(url):
    """Scrape article page to get date and content"""
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find date - look for "Published On" text
        date_text = None
        page_text = soup.get_text()
        match = re.search(r'Published On\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),?\s+(\d{4})', page_text)
        if match:
            date_text = f"{match.group(1)} {match.group(2)}, {match.group(3)}"
        
        # Find content
        news_div = soup.find('div', class_='article-section__body__news')
        content = ''
        if news_div:
            # Get text, clean up ads and extra whitespace
            text = news_div.get_text()
            # Remove "Advt" markers
            text = re.sub(r'\s*Advt\s*', ' ', text)
            # Clean whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            content = text
        
        return date_text, content
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None, ''


def save_articles(articles):
    """Save articles to CSV with clean formatting"""
    save_to_csv(articles, CSV_FILE, SOURCE)


def scrape(existing_links=None):
    """
    Main scrape function
    
    1. Fetch multiple pages
    2. Get all article links
    3. Skip already scraped
    4. Scrape content
    5. Save to CSV
    """
    import time
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count economictimes articles specifically
    et_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        et_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from ET Energy: {et_count} articles")
    
    all_links = []
    
    for news_url in NEWS_URLS:
        print(f"\n--- Checking {news_url} ---")
        try:
            response = requests.get(news_url, headers=headers, timeout=TIMEOUT)
            print(f"Status: {response.status_code}")
        except Exception as e:
            print(f"Error fetching page: {e}")
            continue
        
        soup = BeautifulSoup(response.content, 'html.parser')
        links = get_article_links(soup)
        all_links.extend(links)
        time.sleep(1)  # Be nice to the server
    
    # Remove duplicates
    unique_links = list(set(all_links))
    print(f"\nFound {len(unique_links)} article links")
    
    # Filter out already scraped
    new_links = [link for link in unique_links if link not in existing_links]
    print(f"New links to check: {len(new_links)}")
    
    if not new_links:
        print("No new articles to scrape.")
        return []
    
    # Parallel fetch all articles
    def fetch_with_date(url):
        """Fetch article and extract date + content together"""
        date_text, content = get_article_date_and_content(url)
        if date_text and content:
            return f"DATE:{date_text}|||{content}"
        return ''
    
    # Build article list for parallel fetch (using date placeholder)
    articles_to_fetch = [{'link': link, 'date': ''} for link in new_links]
    
    print(f"\nFetching {len(articles_to_fetch)} articles in parallel...")
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    results = []
    completed = 0
    total = len(articles_to_fetch)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_link = {executor.submit(fetch_with_date, a['link']): a['link'] for a in articles_to_fetch}
        
        for future in as_completed(future_to_link):
            completed += 1
            link = future_to_link[future]
            try:
                result = future.result()
                if result and result.startswith('DATE:'):
                    # Parse date and content from combined result
                    parts = result[5:].split('|||', 1)
                    if len(parts) == 2:
                        date_text, content = parts
                        print(f"  [{completed}/{total}] ✓ Fetched ({len(content)} chars): {link[:50]}...")
                        results.append({
                            'source': SOURCE,
                            'date': standardize_date(date_text),
                            'link': link,
                            'content': clean_content(content)
                        })
                    else:
                        print(f"  [{completed}/{total}] ✗ Parse error: {link[:50]}...")
                else:
                    print(f"  [{completed}/{total}] ✗ No date/content: {link[:50]}...")
            except Exception as e:
                print(f"  [{completed}/{total}] ✗ Error: {link[:50]}... ({e})")
    
    print(f"\nCompleted: {len(results)} articles fetched successfully")
    
    return results


# For standalone testing
if __name__ == "__main__":
    print("=" * 60)
    print(f"ET Energy Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
