"""
Shared Utilities for Oil & Gas Scrapers
========================================
Common functions for:
- Date standardization (YYYY-MM-DD format)
- Content cleaning (remove junk text)
- CSV saving with proper formatting
- Parallel article fetching for speed
"""

import re
import shutil
from datetime import datetime
import pandas as pd
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Standard date format for all scrapers
DATE_FORMAT = '%Y-%m-%d'

# Backup directory
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')

# Junk patterns to remove from article content
JUNK_PATTERNS = [
    # OGJ header/footer text
    r'^Covering the operations of the oil and gas industry\s*',
    r'Covering the operations of the oil and gas industry\s*',
    r'Chris brings \d+ years of experience.*?midstream and transportation sectors\.',
    r'This content is sponsored by:.*$',
    r'Click the button to Download!.*$',
    r'Interested in future Oil & Gas Breakfast Series events\?.*?2026!',
    r'Interested in where things stand on Permian basin.*?Download!',
    
    # BOE Report header/metadata junk
    r'^BOE Report\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+\d{4}\s*\d+:\d+\s*(AM|PM)\s*',
    r'BOE Report\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+\d{4}\s*\d+:\d+\s*(AM|PM)\s*',
    r'(Reuters|Newsfile Corp|Business Wire|PR Newswire|GlobeNewswire)\s*\d*\s*Comments?\s*',
    
    # EnergyNow footer/junk
    r'More results\.\.\.\s*',
    r'FEATURED EVENT\s+VIEW ALL\s+COMMODITIES.*$',
    r'EnergyNow\.com is an energy news media service.*?right now!',
    r'Help us to improve EnergyNow.*?feedback',
    r'Privacy Policy \| Terms of Use.*$',
    r'Get the Latest US Focused Energy News Delivered to You!.*?Quick Sign-Up Here',
    r"It's FREE: Quick Sign-Up Here",
    r'More News Articles\s*',
    
    # Article list navigation junk (repeated article titles in footer)
    r'(Sanctioned Tanker Hyperion.*?Baker Hughes\s*)+',
    r'(North Dakota Rig Count.*?Baker Hughes\s*)+',
    r'(US Drillers Cut Oil and Gas Rigs.*?Baker Hughes\s*)+',
    r'(Dakota Access Pipeline.*?Says\s*)+',
    r'(US Energy Department Signs AI.*?Mission\s*)+',
    r'(US Investor Group Kimmeridge.*?Reports\s*)+',
    r'(TotalEnergies Wins.*?Malaysia\s*)+',
    r'(COMMENTARY:.*?Cuts\s*)+',
    
    # Social sharing and navigation
    r'Share This:.*?(?=\s{2,}|$)',
    r'Share\s*X\s*Facebook\s*Linkedin.*?(?=\s{2,}|$)',
    r'Purchase Licensing Rights.*?(?=\s{2,}|$)',
    r'Sign up for the BOE Report.*',
    r'Successfully subscribed.*',
    r'BOE Network.*',
    r'© \d{4}.*?Ltd\.',
    r'—Please choose an option—.*',
    r'AboutAbout BOEReport.*',
    r'Get In Touch.*?Report Error',
    r'ResourcesWidgets.*?E-mail',
    r'EditorialWebsite/Functionality',
    
    # Reuters specific
    r',?\s*opens new tab',
    r'REUTERS/[A-Za-z\s/]+(?:\s*Purchase)?',
    r'Reuters/[A-Za-z\s/]+',
    r'via REUTERS',
    r'cnsphoto via REUTERS',
    
    # Form elements and misc
    r'Name\s+E-mail.*?Description',
    r'What kind of error\?.*?Functionality',
    r'Note: The page you are currently on.*?specify\.',
    r'Previous Article\s*Â?.*?(?=\s{2,}|[A-Z])',
    r'Next Article.*?(?=\s{2,}|$)',
    r'Suggested Topics:.*?(?=\s{2,}|$)',
    r'Our Standards:.*?Principles\.',
    r'Companies\s+[A-Za-z\s]+Follow\s*',
    r'Follow\s+[A-Z][a-z]+\s+Follow',
    r'Show more companies',
    r'Email\s*X?\s*$',
    
    # Email addresses (author bio junk)
    r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    
    # Author bios
    r'Ciruzzi is a journalist based in.*?finance\.',
    
    # Encoding artifacts
    r'Â\s*',
    r'\u00a0',  # Non-breaking space
    r'&#\d+;',  # HTML entities
]

# Minimum content requirements
MIN_CONTENT_LENGTH = 100


def standardize_date(date_input) -> str:
    """
    Convert various date formats to standard YYYY-MM-DD format.
    
    Accepts:
    - datetime.date object
    - datetime.datetime object  
    - String in various formats
    
    Returns:
    - Standardized date string (YYYY-MM-DD)
    - Empty string if parsing fails
    """
    if date_input is None:
        return ''
    
    # Already a date/datetime object
    if isinstance(date_input, datetime):
        return date_input.strftime(DATE_FORMAT)
    
    if hasattr(date_input, 'strftime'):  # date object
        return date_input.strftime(DATE_FORMAT)
    
    # String input - try various formats
    date_str = str(date_input).strip()
    
    if not date_str:
        return ''
    
    # List of possible date formats to try
    date_formats = [
        '%Y-%m-%d',           # 2025-12-20
        '%B %d, %Y',          # December 20, 2025
        '%b %d, %Y',          # Dec 20, 2025
        '%b. %d, %Y',         # Dec. 20, 2025
        '%d %B %Y',           # 20 December 2025
        '%d %b %Y',           # 20 Dec 2025
        '%m/%d/%Y',           # 12/20/2025
        '%d/%m/%Y',           # 20/12/2025
        '%Y/%m/%d',           # 2025/12/20
        '%B %d %Y',           # December 20 2025
        '%b %d %Y',           # Dec 20 2025
        '%d-%m-%Y',           # 20-12-2025
        '%m-%d-%Y',           # 12-20-2025
        '%Y-%b-%d',           # 2025-Dec-19 (offshore-energy format)
    ]
    
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime(DATE_FORMAT)
        except ValueError:
            continue
    
    # Try to extract date from longer strings (e.g., "Dec 19, 2025 at 12:40")
    # Pattern: Month Day, Year
    patterns = [
        (r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})', '%B %d %Y'),
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', '%b %d %Y'),
        (r'(\d{4})-(\d{2})-(\d{2})', None),  # Already YYYY-MM-DD
    ]
    
    for pattern, fmt in patterns:
        match = re.search(pattern, date_str)
        if match:
            if fmt is None:  # Already in YYYY-MM-DD
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            try:
                extracted = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                parsed = datetime.strptime(extracted, fmt)
                return parsed.strftime(DATE_FORMAT)
            except ValueError:
                continue
    
    # Could not parse - return empty string
    print(f"  Warning: Could not parse date '{date_str}'")
    return ''


def clean_content(content: str) -> str:
    """
    Clean article content by removing junk text and normalizing whitespace.
    
    Returns:
    - Cleaned content string
    - Empty string if content is invalid
    """
    if not content:
        return ''
    
    content = str(content)
    
    # Remove junk patterns
    for pattern in JUNK_PATTERNS:
        try:
            content = re.sub(pattern, ' ', content, flags=re.IGNORECASE | re.DOTALL)
        except:
            pass
    
    # Normalize whitespace
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    # Remove common trailing junk
    trailing_patterns = [
        r'\s*Sign up for.*$',
        r'\s*Successfully subscribed.*$',
        r'\s*BOE Network.*$',
        r'\s*© \d{4}.*$',
        r'\s*Email\s*X?\s*$',
    ]
    for pattern in trailing_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    return content.strip()


def is_valid_content(content: str) -> bool:
    """Check if content meets minimum quality requirements."""
    if not content:
        return False
    
    content = str(content).strip()
    
    # Check minimum length
    if len(content) < MIN_CONTENT_LENGTH:
        return False
    
    # Check if mostly text (not just special chars)
    alpha_count = sum(c.isalpha() for c in content)
    if alpha_count < len(content) * 0.4:
        return False
    
    return True


def save_to_csv(articles: list, csv_file: str, source_name: str = None, max_retries: int = 3):
    """
    Save articles to CSV with proper formatting.
    Creates daily backup before saving.
    
    Args:
        articles: List of article dicts with keys: source, date, link, content
        csv_file: Path to CSV file
        source_name: Optional source name to filter existing articles
        max_retries: Number of retries for permission errors
    """
    import time
    
    if not articles:
        print("No articles to save.")
        return
    
    # Create backup before modifying
    if os.path.exists(csv_file):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_name = f"articles_backup_{datetime.now().strftime('%Y%m%d')}.csv"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        if not os.path.exists(backup_path):  # Only one backup per day
            shutil.copy2(csv_file, backup_path)
            print(f"  Backup created: {backup_name}")
    
    # Clean and validate articles before saving
    cleaned_articles = []
    for article in articles:
        # Standardize date
        article['date'] = standardize_date(article.get('date', ''))
        
        # Clean content
        article['content'] = clean_content(article.get('content', ''))
        
        # Only keep valid articles
        if is_valid_content(article['content']):
            cleaned_articles.append(article)
        else:
            print(f"  Skipping article with invalid content: {article.get('link', 'unknown')[:50]}")
    
    if not cleaned_articles:
        print("No valid articles to save after cleaning.")
        return
    
    new_df = pd.DataFrame(cleaned_articles)
    
    # Ensure column order
    columns = ['source', 'date', 'link', 'content']
    for col in columns:
        if col not in new_df.columns:
            new_df[col] = ''
    new_df = new_df[columns]
    
    # Load existing and combine
    if os.path.exists(csv_file):
        try:
            existing_df = pd.read_csv(csv_file)
            for col in columns:
                if col not in existing_df.columns:
                    existing_df[col] = ''
            existing_df = existing_df[columns]
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['link'], keep='last')
        except Exception as e:
            print(f"Warning: Error reading existing CSV: {e}")
            combined_df = new_df
    else:
        combined_df = new_df
    
    # Save with retry logic for permission errors
    for attempt in range(max_retries):
        try:
            combined_df.to_csv(csv_file, index=False)
            print(f"Saved {len(cleaned_articles)} articles to {csv_file}")
            return
        except PermissionError:
            if attempt < max_retries - 1:
                print(f"  File in use, retrying in 2s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(2)
            else:
                print(f"  ERROR: Could not save - file permission denied after {max_retries} attempts")
                raise


def get_existing_links(csv_file: str, source_name: str = None) -> set:
    """
    Get already scraped article links from CSV.
    
    Args:
        csv_file: Path to CSV file
        source_name: Optional source name to filter
        
    Returns:
        Set of already scraped URLs
    """
    if not os.path.exists(csv_file):
        return set()
    
    try:
        df = pd.read_csv(csv_file)
        if source_name and 'source' in df.columns:
            df = df[df['source'] == source_name]
        return set(df['link'].dropna().tolist())
    except Exception as e:
        print(f"Warning: Error reading CSV: {e}")
        return set()


def fetch_articles_parallel(articles: list, fetch_func, max_workers: int = 10, 
                           source_name: str = '', standardize: bool = True) -> list:
    """
    Fetch multiple articles in parallel for faster scraping.
    
    Args:
        articles: List of dicts with 'link' and 'date' keys
        fetch_func: Function that takes URL and returns content string
        max_workers: Number of parallel threads (default 10)
        source_name: Source name for the results
        standardize: Whether to standardize dates and clean content
        
    Returns:
        List of article dicts with 'source', 'date', 'link', 'content'
    """
    if not articles:
        return []
    
    results = []
    completed = 0
    total = len(articles)
    
    def fetch_one(article):
        """Fetch a single article and return result dict"""
        link = article['link']
        date = article['date']
        try:
            content = fetch_func(link)
            return {
                'success': True,
                'source': source_name,
                'date': date,
                'link': link,
                'content': content,
                'chars': len(content) if content else 0
            }
        except Exception as e:
            return {
                'success': False,
                'source': source_name,
                'date': date,
                'link': link,
                'content': '',
                'error': str(e)
            }
    
    print(f"\nFetching {total} articles in parallel (max {max_workers} threads)...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_article = {executor.submit(fetch_one, a): a for a in articles}
        
        # Process as they complete
        for future in as_completed(future_to_article):
            completed += 1
            result = future.result()
            
            if result['success'] and result['chars'] > 100:
                print(f"  [{completed}/{total}] ✓ Fetched ({result['chars']} chars): {result['link'][:50]}...")
            else:
                print(f"  [{completed}/{total}] ✗ Failed: {result['link'][:50]}...")
            
            # Clean and standardize if requested
            if standardize:
                result['date'] = standardize_date(result['date'])
                result['content'] = clean_content(result['content'])
            
            # Build final result
            results.append({
                'source': result['source'],
                'date': result['date'],
                'link': result['link'],
                'content': result['content']
            })
    
    print(f"\nCompleted: {len([r for r in results if r['content']])} successful, "
          f"{len([r for r in results if not r['content']])} failed")
    
    return results
