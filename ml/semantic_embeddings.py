"""
Semantic Embeddings Generator - Incremental Processing
Creates embeddings for articles using SentenceTransformer
"""

import os
import pickle
import json
import hashlib
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer

# Paths
ML_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ML_DIR), 'scrapers')
EMBEDDINGS_PATH = os.path.join(ML_DIR, 'embeddings.pkl')
PROCESSED_PATH = os.path.join(ML_DIR, 'processed_articles.json')


def get_article_hash(title, content):
    """Generate unique hash for article"""
    text = f"{title}|{content}"
    return hashlib.md5(text.encode()).hexdigest()


def load_processed_hashes():
    """Load set of already processed article hashes"""
    if os.path.exists(PROCESSED_PATH):
        with open(PROCESSED_PATH, 'r') as f:
            return set(json.load(f))
    return set()


def save_processed_hashes(hashes):
    """Save processed article hashes"""
    with open(PROCESSED_PATH, 'w') as f:
        json.dump(list(hashes), f)


def create_embeddings(force_rebuild=False):
    """Create embeddings for new articles only (incremental).
    Set force_rebuild=True to regenerate all embeddings from scratch.
    
    Embeddings are stored by content hash to survive article reordering/deletion.
    """
    print("Loading articles...")
    articles_path = os.path.join(DATA_DIR, 'articles.csv')
    
    if not os.path.exists(articles_path):
        print("No articles.csv found!")
        return
    
    df = pd.read_csv(articles_path)
    print(f"Found {len(df)} articles in CSV")
    
    # Load existing embeddings (stored by hash)
    embeddings_by_hash = {}
    
    if os.path.exists(EMBEDDINGS_PATH) and not force_rebuild:
        with open(EMBEDDINGS_PATH, 'rb') as f:
            data = pickle.load(f)
            # New format: embeddings stored by hash
            if 'embeddings_by_hash' in data:
                embeddings_by_hash = data['embeddings_by_hash']
                print(f"Loaded {len(embeddings_by_hash)} existing embeddings (hash-indexed)")
            # Old format: convert from index-based by matching with current CSV
            elif 'embeddings' in data:
                old_embeddings = list(data.get('embeddings', []))
                print(f"Found {len(old_embeddings)} embeddings in old format - converting...")
                # Map old embeddings to hashes based on CSV order
                # Assumes embeddings were created in same order as current CSV
                for idx, row in df.iterrows():
                    if idx < len(old_embeddings):
                        title = str(row.get('title', ''))
                        content = str(row.get('content', ''))
                        article_hash = get_article_hash(title, content)
                        embeddings_by_hash[article_hash] = old_embeddings[idx]
                print(f"Converted {len(embeddings_by_hash)} embeddings to hash-indexed format")
    
    # Find articles that need embeddings
    articles_needing_embeddings = []
    
    for idx, row in df.iterrows():
        title = str(row.get('title', ''))
        content = str(row.get('content', ''))
        article_hash = get_article_hash(title, content)
        
        if article_hash not in embeddings_by_hash:
            articles_needing_embeddings.append({
                'idx': idx,
                'hash': article_hash,
                'text': f"{title}. {content[:1000]}"
            })
    
    if not articles_needing_embeddings:
        print("No new articles to process!")
        print(f"Total embeddings: {len(embeddings_by_hash)}")
        # Still rebuild the ordered array for the chatbot
        _save_ordered_embeddings(df, embeddings_by_hash)
        return
    
    print(f"Processing {len(articles_needing_embeddings)} new articles...")
    
    # Load model
    print("Loading SentenceTransformer model...")
    model = SentenceTransformer('all-mpnet-base-v2')
    
    # Create embeddings for new articles
    texts = [a['text'] for a in articles_needing_embeddings]
    print("Creating embeddings...")
    new_embeddings = model.encode(texts, show_progress_bar=True)
    
    # Add new embeddings to hash map
    for i, article in enumerate(articles_needing_embeddings):
        embeddings_by_hash[article['hash']] = new_embeddings[i]
    
    # Save hash-indexed embeddings and ordered array
    _save_ordered_embeddings(df, embeddings_by_hash)
    
    print(f"Done! Total embeddings: {len(embeddings_by_hash)}")
    print(f"New embeddings created: {len(articles_needing_embeddings)}")


def _save_ordered_embeddings(df, embeddings_by_hash):
    """Save embeddings in both hash-indexed format and ordered array format."""
    # Build ordered array matching CSV order (for chatbot compatibility)
    ordered_embeddings = []
    
    for idx, row in df.iterrows():
        title = str(row.get('title', ''))
        content = str(row.get('content', ''))
        article_hash = get_article_hash(title, content)
        
        if article_hash in embeddings_by_hash:
            ordered_embeddings.append(embeddings_by_hash[article_hash])
        else:
            # This shouldn't happen, but create zero vector as fallback
            ordered_embeddings.append(np.zeros(768))
    
    print(f"Saving {len(embeddings_by_hash)} embeddings...")
    with open(EMBEDDINGS_PATH, 'wb') as f:
        pickle.dump({
            'embeddings': np.array(ordered_embeddings),  # For chatbot
            'embeddings_by_hash': embeddings_by_hash,    # For incremental updates
        }, f)
    
    # Update processed hashes file
    save_processed_hashes(set(embeddings_by_hash.keys()))


if __name__ == '__main__':
    create_embeddings()
