"""
Text Classifier for Oil & Gas News
Classifies articles into categories
Supports incremental detection - skips training if no new articles
"""

import os
import pickle
import json
import hashlib
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split

# Paths
ML_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ML_DIR), 'scrapers')
CLASSIFIER_PATH = os.path.join(ML_DIR, 'classifier.pkl')
LABELS_PATH = os.path.join(ML_DIR, 'labels.json')
CLASSIFIER_STATE_PATH = os.path.join(ML_DIR, 'classifier_state.json')

# Category keywords for auto-labeling
CATEGORY_KEYWORDS = {
    'price_market': ['price', 'oil price', 'gas price', 'barrel', 'brent', 'wti', 'crude', 'market', 
                     'trading', 'futures', 'opec', 'demand', 'supply', 'rally', 'drop', 'surge'],
    'production': ['production', 'output', 'drilling', 'well', 'reservoir', 'extraction', 'pump',
                   'bpd', 'barrels per day', 'mcf', 'rig count', 'shale', 'offshore', 'onshore'],
    'pipeline_lng': ['pipeline', 'lng', 'liquefied', 'terminal', 'export', 'import', 'transport',
                     'tanker', 'shipping', 'infrastructure', 'gas pipeline', 'oil pipeline'],
    'geopolitics': ['sanction', 'russia', 'iran', 'saudi', 'opec', 'war', 'conflict', 'embargo',
                    'political', 'government', 'policy', 'diplomacy', 'middle east', 'tension'],
    'corporate': ['merger', 'acquisition', 'deal', 'ceo', 'company', 'earnings', 'profit', 'loss',
                  'revenue', 'stock', 'shares', 'dividend', 'investment', 'capital', 'ipo'],
    'exploration': ['discovery', 'exploration', 'survey', 'seismic', 'prospect', 'find', 'reserve',
                    'basin', 'field', 'block', 'license', 'permit', 'deepwater'],
    'regulation': ['regulation', 'law', 'legislation', 'epa', 'permit', 'compliance', 'environmental',
                   'emission', 'carbon', 'climate', 'renewable', 'transition', 'green'],
    'other': []
}


def auto_label_article(text):
    """Automatically label article based on keywords"""
    text_lower = text.lower()
    scores = {}
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == 'other':
            continue
        score = sum(1 for kw in keywords if kw in text_lower)
        scores[category] = score
    
    if not scores or max(scores.values()) == 0:
        return 'other'
    
    return max(scores, key=scores.get)


def get_data_hash(df):
    """Generate hash of article data to detect changes"""
    content = df['content'].fillna('').str[:200].tolist()
    text = '|'.join(content)
    return hashlib.md5(text.encode()).hexdigest()


def load_classifier_state():
    """Load previous training state"""
    if os.path.exists(CLASSIFIER_STATE_PATH):
        with open(CLASSIFIER_STATE_PATH, 'r') as f:
            return json.load(f)
    return {}


def save_classifier_state(state):
    """Save training state"""
    with open(CLASSIFIER_STATE_PATH, 'w') as f:
        json.dump(state, f)


def train_classifier(force=False, min_new_articles=50):
    """
    Train the text classifier.
    Skips if fewer than min_new_articles since last training (unless force=True).
    """
    print("Loading articles...")
    articles_path = os.path.join(DATA_DIR, 'articles.csv')
    
    if not os.path.exists(articles_path):
        print("No articles.csv found!")
        return
    
    df = pd.read_csv(articles_path)
    current_count = len(df)
    print(f"Found {current_count} articles")
    
    # Check if retraining is needed
    state = load_classifier_state()
    last_count = state.get('article_count', 0)
    new_articles = current_count - last_count
    
    if not force and os.path.exists(CLASSIFIER_PATH):
        if new_articles < min_new_articles:
            print(f"Only {new_articles} new articles since last training (threshold: {min_new_articles})")
            print("Skipping classifier training. Use force=True to override.")
            return state.get('metrics', {})
    
    # Auto-label articles
    print("Auto-labeling articles...")
    df['category'] = df.apply(
        lambda row: auto_label_article(str(row.get('content', ''))), 
        axis=1
    )
    
    # Show distribution
    print("\nCategory distribution:")
    print(df['category'].value_counts())
    
    # Load model for embeddings
    print("\nLoading SentenceTransformer...")
    model = SentenceTransformer('all-mpnet-base-v2')
    
    # Create embeddings
    print("Creating embeddings for training...")
    texts = df['content'].fillna('').str[:500].tolist()
    embeddings = model.encode(texts, show_progress_bar=True)
    
    # Prepare labels
    le = LabelEncoder()
    labels = le.fit_transform(df['category'])
    
    # Filter out classes with less than 2 samples (can't stratify with 1 sample)
    from collections import Counter
    label_counts = Counter(labels)
    valid_mask = [label_counts[l] >= 2 for l in labels]
    
    if sum(valid_mask) < len(labels):
        removed = len(labels) - sum(valid_mask)
        print(f"Removing {removed} samples from classes with only 1 member")
        embeddings = embeddings[valid_mask]
        labels = labels[valid_mask]
        df = df[valid_mask]
    
    # Split data (use stratify only if all classes have 2+ samples)
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, labels, test_size=0.2, random_state=42, stratify=labels
        )
    except ValueError:
        # Fallback without stratification
        print("Warning: Could not stratify, using random split")
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, labels, test_size=0.2, random_state=42
        )
    
    print(f"\nTraining set: {len(X_train)}, Test set: {len(X_test)}")
    
    # Create voting classifier
    print("Training classifier...")
    clf1 = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    clf2 = LogisticRegression(max_iter=1000, random_state=42)
    clf3 = GradientBoostingClassifier(n_estimators=50, random_state=42)
    
    voting_clf = VotingClassifier(
        estimators=[('rf', clf1), ('lr', clf2), ('gb', clf3)],
        voting='soft'
    )
    
    voting_clf.fit(X_train, y_train)
    
    # Evaluate
    train_acc = voting_clf.score(X_train, y_train)
    test_acc = voting_clf.score(X_test, y_test)
    
    print(f"\nTraining accuracy: {train_acc:.2%}")
    print(f"Test accuracy: {test_acc:.2%}")
    
    # Save
    print("\nSaving classifier...")
    with open(CLASSIFIER_PATH, 'wb') as f:
        pickle.dump({
            'classifier': voting_clf,
            'label_encoder': le
        }, f)
    
    # Save labels
    with open(LABELS_PATH, 'w') as f:
        json.dump({
            'classes': le.classes_.tolist(),
            'category_keywords': CATEGORY_KEYWORDS
        }, f, indent=2)
    
    # Save state for incremental detection
    metrics = {'train_accuracy': train_acc, 'test_accuracy': test_acc}
    save_classifier_state({
        'article_count': len(df),
        'metrics': metrics
    })
    
    print("Classifier saved!")
    return metrics


if __name__ == '__main__':
    import sys
    force = '--force' in sys.argv
    train_classifier(force=force)
