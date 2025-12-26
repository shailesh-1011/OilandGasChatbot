"""
OGJ (Oil & Gas Journal) Scraper
================================
Website: https://www.ogj.com/

Sections:
- https://www.ogj.com/general-interest
- https://www.ogj.com/refining-processing
- https://www.ogj.com/drilling-production
- https://www.ogj.com/exploration-development
- https://www.ogj.com/pipelines-transportation

Selectors:
- Date: <div class="date">Dec. 18, 2025</div>
- Article Title: <div class="title-text">
- Skip paid articles with: <span class="iconify i-mdi:lock icon">

Logic:
1. Visit all section pages
2. Check date - only scrape if today or yesterday
3. Skip paid/locked articles
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

SOURCE = 'ogj'
BASE_URL = 'https://www.ogj.com'
NEWS_URLS = [
    'https://www.ogj.com/general-interest',
    'https://www.ogj.com/refining-processing',
    'https://www.ogj.com/drilling-production',
    'https://www.ogj.com/exploration-development',
    'https://www.ogj.com/pipelines-transportation',
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
    """Parse date from text like 'Dec. 18, 2025'"""
    try:
        # Format: Dec. 18, 2025
        return datetime.strptime(date_text.strip(), '%b. %d, %Y').date()
    except:
        pass
    
    try:
        # Format: December 18, 2025
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
    
    # Find all article containers (content-item class)
    article_containers = soup.find_all('div', class_='content-item')
    
    for container in article_containers:
        # Skip paid/locked articles with lock icon
        lock_icon = container.find('span', class_=lambda c: c and 'lock' in ' '.join(c) if c else False)
        if lock_icon:
            print(f"  ⊘ Skipping paid article (lock icon)")
            continue
        
        # Skip industry-statistics (paid content)
        section_link = container.find('a', class_='section-name')
        if section_link and 'industry-statistics' in str(section_link.get('href', '')):
            print(f"  ⊘ Skipping paid article (industry-statistics)")
            continue
        
        # Find article link
        a_tag = container.find('a', class_='title-wrapper')
        if not a_tag or not a_tag.get('href'):
            continue
        
        link = a_tag['href']
        if not link.startswith('http'):
            link = BASE_URL + link
        
        # Find date
        date_div = container.find('div', class_='date')
        date_text = date_div.get_text().strip() if date_div else None
        
        # Check if has valid date
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
        
        # Find article body
        article_body = soup.find('div', class_='article-body') or soup.find('article')
        
        if article_body:
            paragraphs = article_body.find_all('p')
        else:
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
    
    1. Fetch all section pages
    2. Filter by date (today/yesterday only)
    3. Skip paid articles
    4. Skip already scraped links
    5. Scrape content & summarize
    6. Save to CSV
    """
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count OGJ articles specifically
    ogj_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        ogj_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from OGJ: {ogj_count} articles")
    
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
    
    # Remove duplicates
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
    print(f"OGJ Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
