"""
Indian Oil & Gas Scraper
=========================
Website: https://www.indianoilandgas.com/

Selectors:
- News section: <td class="centercontent"> (index 1 contains news)
- Headlines: <b> tags
- Article links: <a href="viewnews.php?id=XXXXX">more..</a>
- Date: In article text "December 20, 2025:"
- Article Content: <td> containing full article text

Logic:
1. Visit homepage
2. Find news section (centercontent td index 1)
3. Extract headlines, dates, and article links
4. Filter to today/yesterday only
5. Visit article pages for full content
7. Save to CSV
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

SOURCE = 'indianoilandgas'
BASE_URL = 'https://www.indianoilandgas.com'
NEWS_URL = 'https://www.indianoilandgas.com/'
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
    """Parse date from text like 'December 20, 2025'"""
    try:
        # Format: December 20, 2025
        return datetime.strptime(date_text.strip(), '%B %d, %Y').date()
    except:
        pass
    try:
        # Format: Dec 20, 2025
        return datetime.strptime(date_text.strip(), '%b %d, %Y').date()
    except:
        return None


def is_recent(date_text):
    """Check if date is recent - DISABLED: collecting all articles for training"""
    # DATE FILTERING DISABLED - Collecting all articles for NLP training
    return True


def get_article_links(soup):
    """Extract article links from the news section"""
    articles = []
    
    # Find news section - it's the second centercontent td (index 1)
    tds = soup.find_all('td', class_='centercontent')
    if len(tds) < 2:
        print("Could not find news section")
        return articles
    
    news_td = tds[1]
    
    # Get the HTML content and split by <hr> to get individual articles
    html_content = str(news_td)
    
    # Find all bold headlines and their associated links
    headlines = news_td.find_all('b')
    links = news_td.find_all('a', href=True)
    
    # Match headlines with links
    for i, headline in enumerate(headlines):
        title = headline.get_text().strip()
        
        # Find the corresponding link
        if i < len(links):
            link_tag = links[i]
            href = link_tag.get('href', '')
            
            if 'viewnews.php' not in href:
                continue
            
            # Make absolute URL
            link = BASE_URL + '/' + href if not href.startswith('http') else href
            
            # Find date - look for text after headline
            next_sibling = headline.next_sibling
            date_text = None
            
            # Search for date pattern in nearby text
            parent_text = str(headline.parent) if headline.parent else ''
            date_match = re.search(r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})', parent_text)
            
            if date_match:
                date_text = date_match.group(1)
            
            if date_text:
                articles.append({
                    'link': link,
                    'date': date_text,
                    'title': title
                })
                print(f"  ✓ Found ({date_text}): {title[:50]}...")
    
    return articles


def get_article_content(url):
    """Scrape article content from article page"""
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the main article content - look for td with article text
        tds = soup.find_all('td')
        
        for td in tds:
            text = td.get_text()
            # Look for the td that starts with "Today's News" or contains the date pattern
            if "Today's News" in text or re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}:', text):
                # Clean up the text
                content = text.strip()
                # Remove "Today's News »" prefix
                content = re.sub(r"Today's News\s*»\s*", '', content)
                return content
        
        return ''
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ''


def save_articles(articles):
    """Save articles to CSV with clean formatting"""
    save_to_csv(articles, CSV_FILE, SOURCE)


def scrape(existing_links=None):
    """
    Main scrape function
    
    1. Fetch homepage
    2. Extract news articles from news section
    3. Skip already scraped links
    4. Scrape content
    5. Save to CSV
    """
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count indianoilandgas articles specifically
    iog_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        iog_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from Indian Oil & Gas: {iog_count} articles")
    
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
    print(f"Indian Oil & Gas Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
