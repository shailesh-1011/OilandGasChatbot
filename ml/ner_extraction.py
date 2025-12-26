"""
Named Entity Recognition for Oil & Gas News
Extracts companies, locations, prices, etc.
"""

import os
import json
import hashlib
import re
import pandas as pd
from collections import defaultdict

# Paths
ML_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ML_DIR), 'scrapers')
ENTITIES_PATH = os.path.join(ML_DIR, 'entities.json')
NER_PROCESSED_PATH = os.path.join(ML_DIR, 'ner_processed.json')

# Known entities
OIL_GAS_COMPANIES = [
    'ExxonMobil', 'Chevron', 'Shell', 'BP', 'TotalEnergies', 'ConocoPhillips',
    'Occidental', 'EOG Resources', 'Pioneer', 'Devon Energy', 'Hess',
    'Marathon Oil', 'Apache', 'Diamondback', 'Coterra', 'APA Corporation',
    'Saudi Aramco', 'Gazprom', 'Rosneft', 'PetroChina', 'Sinopec', 'CNOOC',
    'Petrobras', 'Equinor', 'Eni', 'Repsol', 'OMV', 'Woodside', 'Santos',
    'ONGC', 'Reliance', 'ADNOC', 'QatarEnergy', 'Kuwait Oil', 'NIOC',
    'Schlumberger', 'Halliburton', 'Baker Hughes', 'Weatherford', 'NOV'
]

LOCATIONS = [
    'Permian Basin', 'Eagle Ford', 'Bakken', 'Marcellus', 'Haynesville',
    'Gulf of Mexico', 'North Sea', 'Caspian Sea', 'South China Sea',
    'Persian Gulf', 'Arabian Gulf', 'Mediterranean', 'offshore Brazil',
    'offshore Guyana', 'offshore Namibia', 'offshore Suriname',
    'Texas', 'Oklahoma', 'North Dakota', 'Louisiana', 'Alaska',
    'Alberta', 'British Columbia', 'Saudi Arabia', 'UAE', 'Kuwait',
    'Iraq', 'Iran', 'Russia', 'Norway', 'UK', 'Nigeria', 'Angola',
    'Libya', 'Algeria', 'Venezuela', 'Brazil', 'Mexico', 'China', 'India'
]


def get_article_hash(title, content):
    """Generate unique hash for article"""
    text = f"{title}|{content}"
    return hashlib.md5(text.encode()).hexdigest()


def load_processed_hashes():
    """Load set of already processed article hashes"""
    if os.path.exists(NER_PROCESSED_PATH):
        with open(NER_PROCESSED_PATH, 'r') as f:
            return set(json.load(f))
    return set()


def save_processed_hashes(hashes):
    """Save processed article hashes"""
    with open(NER_PROCESSED_PATH, 'w') as f:
        json.dump(list(hashes), f)


def extract_prices(text):
    """Extract price mentions"""
    prices = []
    patterns = [
        r'\$(\d+(?:\.\d+)?)\s*(?:per\s+)?(?:barrel|bbl)',
        r'\$(\d+(?:\.\d+)?)/(?:barrel|bbl)',
        r'(\d+(?:\.\d+)?)\s*dollars?\s*(?:per\s+)?(?:barrel|bbl)',
        r'\$(\d+(?:\.\d+)?)\s*(?:per\s+)?(?:mcf|mmbtu)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        prices.extend(matches)
    
    return list(set(prices))


def extract_percentages(text):
    """Extract percentage changes"""
    percentages = []
    patterns = [
        r'(\d+(?:\.\d+)?)\s*%',
        r'(\d+(?:\.\d+)?)\s*percent',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        percentages.extend(matches)
    
    return list(set(percentages))


def extract_volumes(text):
    """Extract production volumes"""
    volumes = []
    patterns = [
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million\s+)?(?:barrels?\s+per\s+day|bpd|b/d)',
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million\s+)?(?:cubic\s+feet|mcf|bcf)',
        r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:million|billion)\s*(?:barrels?|boe)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        volumes.extend(matches)
    
    return list(set(volumes))


def extract_entities_from_text(text):
    """Extract all entities from text"""
    entities = {
        'companies': [],
        'locations': [],
        'prices': [],
        'percentages': [],
        'volumes': [],
        'dates': []
    }
    
    text_lower = text.lower()
    
    # Companies
    for company in OIL_GAS_COMPANIES:
        if company.lower() in text_lower:
            entities['companies'].append(company)
    
    # Locations
    for location in LOCATIONS:
        if location.lower() in text_lower:
            entities['locations'].append(location)
    
    # Prices
    entities['prices'] = extract_prices(text)
    
    # Percentages
    entities['percentages'] = extract_percentages(text)
    
    # Volumes
    entities['volumes'] = extract_volumes(text)
    
    # Dates
    date_pattern = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
    entities['dates'] = re.findall(date_pattern, text, re.IGNORECASE)
    
    return entities


def extract_all_entities():
    """Extract entities from all articles (incremental)"""
    print("Loading articles...")
    articles_path = os.path.join(DATA_DIR, 'articles.csv')
    
    if not os.path.exists(articles_path):
        print("No articles.csv found!")
        return
    
    df = pd.read_csv(articles_path)
    print(f"Found {len(df)} articles")
    
    # Load existing entities
    all_entities = {}
    if os.path.exists(ENTITIES_PATH):
        with open(ENTITIES_PATH, 'r', encoding='utf-8') as f:
            all_entities = json.load(f)
        print(f"Loaded {len(all_entities)} existing entity records")
    
    # Load processed hashes
    processed_hashes = load_processed_hashes()
    print(f"Already processed: {len(processed_hashes)} articles")
    
    # Find new articles
    new_count = 0
    
    for idx, row in df.iterrows():
        title = str(row.get('title', ''))
        content = str(row.get('content', ''))
        article_hash = get_article_hash(title, content)
        
        if article_hash in processed_hashes:
            continue
        
        # Extract entities
        text = f"{title}. {content}"
        entities = extract_entities_from_text(text)
        
        # Store
        all_entities[str(idx)] = {
            'title': title[:100],
            'entities': entities
        }
        
        processed_hashes.add(article_hash)
        new_count += 1
    
    if new_count == 0:
        print("No new articles to process!")
    else:
        print(f"Processed {new_count} new articles")
    
    # Save
    print("Saving entities...")
    with open(ENTITIES_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_entities, f, indent=2)
    
    save_processed_hashes(processed_hashes)
    
    # Summary
    all_companies = set()
    all_locations = set()
    
    for record in all_entities.values():
        entities = record.get('entities', {})
        all_companies.update(entities.get('companies', []))
        all_locations.update(entities.get('locations', []))
    
    print(f"\nEntity Summary:")
    print(f"  Total records: {len(all_entities)}")
    print(f"  Unique companies: {len(all_companies)}")
    print(f"  Unique locations: {len(all_locations)}")
    
    return all_entities


if __name__ == '__main__':
    extract_all_entities()
