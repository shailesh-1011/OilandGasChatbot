"""
Reuters Energy Scraper
=======================
Website: https://www.reuters.com/business/energy/

Selectors:
- Articles: <a href="/business/energy/..."> with date in URL (YYYY-MM-DD)
- Article content: <div data-testid="ArticleBody">
- Fallback: meta og:description for summary
- Date: Extracted from URL pattern (2025-12-19)

Logic:
1. Visit energy section page with browser cookies
2. Extract article links with dates in URLs
3. Filter to today/yesterday only
4. Visit article pages for content
6. Save to CSV

NOTE: Reuters requires browser cookies to bypass bot protection.
Update cookies periodically from browser DevTools.
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd
import os
import re
from datetime import datetime, timedelta
from scrapers.utils import standardize_date, clean_content, save_to_csv, get_existing_links as get_links, fetch_articles_parallel

SOURCE = 'reuters'
BASE_URL = 'https://www.reuters.com'
NEWS_URL = 'https://www.reuters.com/business/energy/'
CSV_FILE = os.path.join(os.path.dirname(__file__), 'articles.csv')
TIMEOUT = 30  # seconds

# Browser cookies - UPDATE THESE FROM YOUR BROWSER WHEN EXPIRED
cookies = {
    '_ga_WBSR7WLTGD': 'GS2.1.s1766238162$o1$g1$t1766238366$j41$l0$h0',
    'cleared-onetrust-cookies': 'Thu, 17 Feb 2022 19:17:07 GMT',
    'usprivacy': '1---',
    '_gcl_au': '1.1.193808163.1766238158',
    'ABTastySession': 'mrasn=&lp=https%253A%252F%252Fwww.reuters.com%252Fbusiness%252Fenergy%252F%253Futm_source%253Dchatgpt.com',
    '_fbp': 'fb.1.1766238158548.49212085267751477',
    'permutive-id': '3d49f7b9-dac5-4280-be5d-4391acf2aa7e',
    'dicbo_id': '%7B%22dicbo_fetch%22%3A1766238159336%7D',
    '_cb': 'CP1pGYDlgybXBnm2qe',
    '_cb_svref': 'https%3A%2F%2Fchatgpt.com%2F',
    'ajs_anonymous_id': '9828c804-1538-4a77-9263-c236d9b71d8a',
    '_pbjs_userid_consent_data': '3524755945110770',
    '_v__chartbeat3': 'CYUciBy5qBpDsYGlD',
    '_ga': 'GA1.2.603389167.1766238161',
    '_gid': 'GA1.2.1707696258.1766238161',
    'BOOMR_CONSENT': '"opted-in"',
    '_gat': '1',
    'OneTrustWPCCPAGoogleOptOut': 'false',
    'sailthru_pageviews': '2',
    'OptanonConsent': 'isGpcEnabled=0&datestamp=Sat+Dec+20+2025+19%3A16%3A00+GMT%2B0530+(India+Standard+Time)&version=202509.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=9d63ae63-0ad7-4966-98a5-31f706b97080&interactionCount=1&isAnonUser=1&landingPath=https%3A%2F%2Fwww.reuters.com%2Fbusiness%2Fenergy%2F%3Futm_source%3Dchatgpt.com&groups=1%3A1%2C2%3A1%2C3%3A1%2C4%3A1',
    'ABTasty': 'uid=hf4r097n7a341ntm&fst=1766238158150&pst=-1&cst=1766238158150&ns=1&pvt=2&pvis=2&th=1530618.0.2.2.1.1.1766238158918.1766238360892.0.1_1546109.1927024.2.2.1.1.1766238158162.1766238360323.0.1',
    'datadome': 'U5oyBzd8Sxdh0ng8gCNkvNhXOmoMrGyNsHfjufBBEQ4cpUEt8YdVaxK3mdVZdr_VgofsJZNkZmJl_Z8NmAafgcRYH_jB14bv4VxcyrQp2hUO6CtW6z8EhgH3FoCr6Ljb',
    'sailthru_visitor': '2b7d3014-5a39-4395-a285-33b024d14004',
    '_chartbeat2': '.1766238159595.1766238362826.1.BgdMQOgh-ddDIhLWxP9WycDfXZwy.2',
    '_awl': '2.1766238367.5-2cda674c0c88edcd8c4448409dda0ce0-6763652d617369612d6561737431-1',
    '_dd_s': 'rum=0&expire=1766239267875',
}

headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-US,en;q=0.9',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
}


def get_existing_links():
    """Load existing article links to avoid duplicates"""
    return get_links(CSV_FILE, SOURCE)


def extract_date_from_url(url):
    """Extract date from URL like /business/energy/article-title-2025-12-19/"""
    match = re.search(r'-(\d{4})-(\d{2})-(\d{2})/?$', url)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day)).date()
        except:
            pass
    return None


def extract_date_from_time_element(container):
    """Extract date from time element with datetime attribute"""
    time_elem = container.find('time', attrs={'data-testid': 'Text'})
    if time_elem and time_elem.get('datetime'):
        try:
            dt = datetime.fromisoformat(time_elem['datetime'].replace('Z', '+00:00'))
            return dt.date()
        except:
            pass
    return None


def get_article_links(soup):
    """Extract article links from energy section page using multiple selectors"""
    articles = []
    seen = set()
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # Method 1: BasicCard articles (a[data-testid="Title"])
    title_links = soup.find_all('a', attrs={'data-testid': 'Title'})
    for link in title_links:
        href = link.get('href', '')
        if not href.startswith('/business/energy/'):
            continue
        if href in seen:
            continue
        
        title = link.get_text().strip()
        if not title or len(title) < 10:
            continue
        
        # Find parent container to get datetime
        container = link.find_parent('div', attrs={'data-testid': ['BasicCard', 'HubCard']})
        article_date = None
        if container:
            article_date = extract_date_from_time_element(container)
        
        # Fallback to URL date extraction
        if not article_date:
            article_date = extract_date_from_url(href)
        
        seen.add(href)
        full_url = BASE_URL + href
        
        # DATE FILTERING DISABLED - Collecting all articles for NLP training
        date_str = article_date.strftime('%B %d, %Y') if article_date else 'Unknown'
        articles.append({
            'link': full_url,
            'date': date_str,
            'title': title
        })
        print(f"  ✓ Found ({date_str}): {title[:50]}...")
    
    # Method 2: AuthorStoryCard articles
    author_cards = soup.find_all('a', attrs={'data-testid': 'AuthorStoryCard'})
    for link in author_cards:
        href = link.get('href', '')
        if not href.startswith('/business/energy/'):
            continue
        if href in seen:
            continue
        if '--reeii-' in href:  # Skip premium articles
            continue
        
        # Get title from nested h3/span
        title_elem = link.find(['h3', 'span'], attrs={'data-testid': 'Heading'})
        if title_elem:
            title = title_elem.get_text().strip()
        else:
            title = link.get_text().strip()
        
        if not title or len(title) < 10:
            continue
        
        article_date = extract_date_from_time_element(link)
        if not article_date:
            article_date = extract_date_from_url(href)
        
        seen.add(href)
        full_url = BASE_URL + href
        
        # DATE FILTERING DISABLED - Collecting all articles for NLP training
        date_str = article_date.strftime('%B %d, %Y') if article_date else 'Unknown'
        articles.append({
            'link': full_url,
            'date': date_str,
            'title': title
        })
        print(f"  ✓ Found AuthorCard ({date_str}): {title[:50]}...")
    
    # Method 3: Fallback - scan ALL links with /business/energy/ href
    all_links = soup.find_all('a', href=True)
    for link in all_links:
        href = link.get('href', '')
        
        if not href.startswith('/business/energy/'):
            continue
        if href.count('/') < 4:  # Need full article path
            continue
        if '--reeii-' in href:  # Skip premium articles
            continue
        if href in seen:
            continue
        
        title = link.get_text().strip()
        if not title or len(title) < 10:
            continue
        
        # Try to find date from nearest time element
        parent = link.find_parent(['li', 'div', 'article'])
        article_date = None
        if parent:
            article_date = extract_date_from_time_element(parent)
        
        # Fallback to URL date extraction
        if not article_date:
            article_date = extract_date_from_url(href)
        
        seen.add(href)
        full_url = BASE_URL + href
        
        # DATE FILTERING DISABLED - Collecting all articles for NLP training
        date_str = article_date.strftime('%B %d, %Y') if article_date else 'Unknown'
        articles.append({
            'link': full_url,
            'date': date_str,
            'title': title
        })
        print(f"  ✓ Found Fallback ({date_str}): {title[:50]}...")

    
    return articles


def get_article_content(url):
    """Scrape article content from article page"""
    try:
        response = requests.get(url, cookies=cookies, headers=headers, timeout=TIMEOUT)
        if response.status_code != 200:
            print(f"  ✗ HTTP {response.status_code}")
            return ''
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to get article body
        article_div = soup.find('div', attrs={'data-testid': 'ArticleBody'})
        if article_div:
            text = article_div.get_text(separator=' ', strip=True)
            # Clean up - remove common footer text
            text = re.sub(r'Reporting by.*$', '', text, flags=re.IGNORECASE)
            text = re.sub(r'Sign up\s+here\.?', '', text, flags=re.IGNORECASE)
            text = re.sub(r'Our Standards:.*$', '', text, flags=re.IGNORECASE)
            return text.strip()
        
        # Fallback: use meta description
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            return og_desc.get('content', '')
        
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
    
    1. Fetch energy section page
    2. Extract article links with dates
    3. Filter by date (today/yesterday only)
    4. Skip already scraped links
    5. Scrape content & summarize
    6. Save to CSV
    """
    if existing_links is None:
        existing_links = get_existing_links()
    
    # Count reuters articles specifically
    reuters_count = 0
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        reuters_count = len(df[df['source'] == SOURCE])
    
    print(f"Already scraped from Reuters: {reuters_count} articles")
    
    try:
        response = requests.get(NEWS_URL, cookies=cookies, headers=headers, timeout=TIMEOUT)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print("\n⚠️  ACCESS DENIED - Cookies may be expired!")
            print("Please update cookies in the script from your browser.")
            return []
            
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
    print(f"Reuters Energy Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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
