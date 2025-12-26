"""
Topic Clustering for Oil & Gas News
Groups similar articles into clusters
Supports incremental detection - skips if no new articles
"""

import os
import pickle
import json
import hashlib
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sentence_transformers import SentenceTransformer
from collections import Counter

# Paths
ML_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ML_DIR), 'scrapers')
CLUSTERS_PATH = os.path.join(ML_DIR, 'clusters.pkl')
EMBEDDINGS_PATH = os.path.join(ML_DIR, 'embeddings.pkl')
CLUSTER_STATE_PATH = os.path.join(ML_DIR, 'cluster_state.json')


def extract_topic_words(texts, n_words=5):
    """Extract common words from texts"""
    words = []
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                  'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
                  'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                  'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'it', 'its',
                  'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they',
                  'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
                  'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
                  'not', 'only', 'same', 'so', 'than', 'too', 'very', 'just', 'also'}
    
    for text in texts:
        text_words = str(text).lower().split()
        text_words = [w.strip('.,!?()[]{}":;') for w in text_words]
        text_words = [w for w in text_words if len(w) > 3 and w not in stop_words and w.isalpha()]
        words.extend(text_words)
    
    counter = Counter(words)
    return [word for word, _ in counter.most_common(n_words)]


def get_data_hash(df):
    """Generate hash of article data to detect changes"""
    content = df['content'].fillna('').str[:200].tolist()
    text = '|'.join(content)
    return hashlib.md5(text.encode()).hexdigest()


def load_cluster_state():
    """Load previous clustering state"""
    if os.path.exists(CLUSTER_STATE_PATH):
        with open(CLUSTER_STATE_PATH, 'r') as f:
            return json.load(f)
    return {}


def save_cluster_state(state):
    """Save clustering state"""
    with open(CLUSTER_STATE_PATH, 'w') as f:
        json.dump(state, f)


def create_clusters(n_clusters=10, force=False):
    """Create topic clusters from articles (skips if no new articles unless force=True)"""
    print("Loading articles...")
    articles_path = os.path.join(DATA_DIR, 'articles.csv')
    
    if not os.path.exists(articles_path):
        print("No articles.csv found!")
        return
    
    df = pd.read_csv(articles_path)
    print(f"Found {len(df)} articles")
    
    # Check if reclustering is needed
    current_hash = get_data_hash(df)
    state = load_cluster_state()
    
    if not force and os.path.exists(CLUSTERS_PATH):
        if state.get('data_hash') == current_hash:
            print("No new articles since last clustering. Skipping...")
            print("Use create_clusters(force=True) to force reclustering")
            return state.get('cluster_info', {})
    
    # Load or create embeddings
    if os.path.exists(EMBEDDINGS_PATH):
        print("Loading existing embeddings...")
        with open(EMBEDDINGS_PATH, 'rb') as f:
            data = pickle.load(f)
            embeddings = data.get('embeddings', np.array([]))
            
        # Check for mismatch
        if len(embeddings) != len(df):
            print(f"WARNING: Embeddings ({len(embeddings)}) don't match articles ({len(df)})")
            print("Skipping clustering - run embeddings rebuild first")
            return None
    else:
        print("Creating embeddings...")
        model = SentenceTransformer('all-mpnet-base-v2')
        texts = df['content'].fillna('').str[:500].tolist()
        embeddings = model.encode(texts, show_progress_bar=True)
    
    if len(embeddings) == 0:
        print("No embeddings available!")
        return
    
    # Adjust n_clusters if needed
    n_clusters = min(n_clusters, len(embeddings))
    
    print(f"\nClustering into {n_clusters} topics...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(embeddings)
    
    # Analyze clusters
    print("\nCluster Analysis:")
    print("-" * 50)
    
    cluster_info = {}
    for cluster_id in range(n_clusters):
        mask = cluster_labels == cluster_id
        cluster_articles = df[mask]
        
        # Get topic words from content
        contents = cluster_articles['content'].fillna('').str[:200].tolist()
        topic_words = extract_topic_words(contents)
        
        cluster_info[cluster_id] = {
            'size': int(mask.sum()),
            'topic_words': topic_words,
            'sample_content': [c[:100] + '...' for c in contents[:3]]
        }
        
        print(f"\nCluster {cluster_id}: {mask.sum()} articles")
        print(f"  Topics: {', '.join(topic_words)}")
    
    # PCA for visualization
    print("\nCreating PCA projection...")
    pca = PCA(n_components=2)
    embeddings_2d = pca.fit_transform(embeddings)
    
    # Save
    print("\nSaving clusters...")
    with open(CLUSTERS_PATH, 'wb') as f:
        pickle.dump({
            'kmeans': kmeans,
            'cluster_labels': cluster_labels,
            'cluster_info': cluster_info,
            'pca': pca,
            'embeddings_2d': embeddings_2d
        }, f)
    
    # Save state for incremental detection
    save_cluster_state({
        'data_hash': current_hash,
        'n_articles': len(df),
        'n_clusters': n_clusters,
        'cluster_info': {str(k): v for k, v in cluster_info.items()}
    })
    
    print("Clustering complete!")
    return cluster_info


if __name__ == '__main__':
    import sys
    force = '--force' in sys.argv
    create_clusters(force=force)
