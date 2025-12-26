"""
Oil & Gas Watch Scraper
========================
Website: https://news.oilandgaswatch.org/

Selectors:
- Date: <div class="text-small dark">December 18, 2025</div>
- Article Link: <a class="button-primary w-button" href="/post/...">Read Article</a>
- Article Content: <p> tags

Logic:
1. Visit articles page
2. Check date - only scrape if today or yesterday
3. Check if link already in CSV - skip if already scraped
4. Scrape article content
6. Save to CSV
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

SOURCE = 'oilandgaswatch'
BASE_URL = 'https://news.oilandgaswatch.org'
NEWS_URL = 'https://news.oilandgaswatch.org/articles'
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
    """Parse date from text like 'December 18, 2025'"""
    try:
        return datetime.strptime(date_text.strip(), '%B %d, %Y').date()
    except:
        return None


def is_recent(date_text):
    """Check if date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def get_article_links(soup):
    """Extract article links from the main page - only for recent articles"""
    articles = []
    
    buttons = soup.find_all('a', class_='button-primary')
    
    for button in buttons:
        if not button.get('href'):
            continue
        
        # Get the link
        link = button['href']
        if not link.startswith('http'):
            link = BASE_URL + link
        
        # Find the date - look in parent/grandparent elements
        parent = button.parent
        date_text = None
        
        # Search up to 5 levels up for the date
        for _ in range(5):
            if parent is None:
                break
            date_divs = parent.find_all('div', class_='text-small')
            for div in date_divs:
                text = div.get_text().strip()
                # Check if it looks like a date (contains month name)
                if any(month in text for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                                                     'July', 'August', 'September', 'October', 'November', 'December']):
                    date_text = text
                    break
            if date_text:
                break
            parent = parent.parent
        
        # Add all articles with dates
        if date_text:
            articles.append({
                'link': link,
                'date': date_text
            })
            print(f"  ✓ Found ({date_text}): {link[:50]}...")
        else:
            print(f"  ? No date found: {link[:50]}...")
    
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
    
    1. Fetch articles page
    2. Skip already scraped links
    3. Scrape content
    4. Save to CSV
    """
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count oilandgaswatch articles specifically
    ogw_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        ogw_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from Oil & Gas Watch: {ogw_count} articles")
    
    try:
        response = requests.get(NEWS_URL, headers=headers, timeout=TIMEOUT)
        print(f"Status: {response.status_code}")
    except Exception as e:
        print(f"Error fetching main page: {e}")
        return []
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print("\nChecking articles...")
    recent_articles = get_article_links(soup)
    
    print(f"\nFound {len(recent_articles)} total articles")
    
    # Filter out already scraped
    new_articles = [a for a in recent_articles if a['link'] not in existing_links]
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
    print(f"Oil & Gas Watch Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
