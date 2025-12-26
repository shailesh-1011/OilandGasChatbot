"""
Oil & Gas Chatbot - Semantic Search with NLP
"""

import os
import pickle
import json
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Paths
ML_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(ML_DIR), 'scrapers')
EMBEDDINGS_PATH = os.path.join(ML_DIR, 'embeddings.pkl')
CLASSIFIER_PATH = os.path.join(ML_DIR, 'classifier.pkl')
LABELS_PATH = os.path.join(ML_DIR, 'labels.json')
ENTITIES_PATH = os.path.join(ML_DIR, 'entities.json')


class OilGasChatbot:
    def __init__(self):
        self.model = None
        self.embeddings = None
        self.articles = None
        self.classifier = None
        self.label_encoder = None
        self.entities = None
        self.loaded = False
    
    def load_models(self):
        """Load all ML models and data"""
        if self.loaded:
            return
        
        print("Loading models...")
        
        # Load sentence transformer
        self.model = SentenceTransformer('all-mpnet-base-v2')
        
        # Load articles
        articles_path = os.path.join(DATA_DIR, 'articles.csv')
        if os.path.exists(articles_path):
            self.articles = pd.read_csv(articles_path)
            self.articles['date'] = pd.to_datetime(self.articles['date'], errors='coerce')
        else:
            self.articles = pd.DataFrame(columns=['title', 'content', 'date', 'source', 'link'])
        
        # Load embeddings
        if os.path.exists(EMBEDDINGS_PATH):
            with open(EMBEDDINGS_PATH, 'rb') as f:
                data = pickle.load(f)
                self.embeddings = data.get('embeddings', np.array([]))
                print(f"Loaded {len(self.embeddings)} embeddings")
        else:
            self.embeddings = np.array([])
        
        # Load classifier
        if os.path.exists(CLASSIFIER_PATH):
            with open(CLASSIFIER_PATH, 'rb') as f:
                data = pickle.load(f)
                self.classifier = data.get('classifier')
                self.label_encoder = data.get('label_encoder')
                # Handle old format with idx_to_label
                if not self.label_encoder and 'idx_to_label' in data:
                    self.idx_to_label = data['idx_to_label']
                else:
                    self.idx_to_label = None
        
        # Load entities
        if os.path.exists(ENTITIES_PATH):
            with open(ENTITIES_PATH, 'r', encoding='utf-8') as f:
                self.entities = json.load(f)
        else:
            self.entities = {}
        
        self.loaded = True
        print("Models loaded successfully!")
    
    def search_articles(self, query, top_k=5):
        """Search articles using semantic similarity"""
        if not self.loaded:
            self.load_models()
        
        if len(self.embeddings) == 0 or len(self.articles) == 0:
            return []
        
        # Encode query
        query_embedding = self.model.encode([query])[0]
        
        # Calculate similarities
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        
        # Extract key terms from query for keyword matching
        query_lower = query.lower()
        
        # Require specific terms for topic-specific queries
        required_terms = []
        
        # Rig count is very specific
        if 'rig count' in query_lower:
            required_terms.extend(['rig count', 'active rigs', 'rigs fell', 'rigs rose'])
        
        # Oil price queries - must have actual price indicators
        if ('price' in query_lower or 'cost' in query_lower) and ('oil' in query_lower or 'crude' in query_lower or 'brent' in query_lower or 'wti' in query_lower):
            required_terms.extend(['brent', 'wti', 'barrel', 'oil price', 'crude price', 'oil fell', 'oil rose', 'oil gained', 'oil dropped'])
        
        # OPEC queries
        if 'opec' in query_lower:
            required_terms.extend(['opec', 'opec+'])
        
        # Get top results
        top_indices = np.argsort(similarities)[::-1][:top_k * 5]  # Get more candidates
        
        results = []
        now = datetime.now()
        
        # First pass: collect results and find the most recent article among top candidates
        candidates = []
        most_recent_date = None
        most_recent_idx = None
        
        for idx in top_indices:
            if idx >= len(self.articles):
                continue
            
            row = self.articles.iloc[idx]
            score = float(similarities[idx])
            content_lower = str(row.get('content', '')).lower()
            content_str = str(row.get('content', ''))
            
            # Check if article contains required terms (if any)
            matches_required = True
            if required_terms:
                matches_required = any(term in content_lower for term in required_terms)
            
            # Only consider articles that match required terms
            if not matches_required:
                continue
            
            # Check article date
            article_date = None
            if pd.notna(row.get('date')):
                try:
                    article_date = pd.to_datetime(row['date'])
                    days_old = (now - article_date).days
                    # Only consider articles within 7 days for recency boost
                    if days_old <= 7:
                        if most_recent_date is None or article_date > most_recent_date:
                            most_recent_date = article_date
                            most_recent_idx = idx
                except:
                    pass
            
            candidates.append({
                'idx': idx,
                'row': row,
                'score': score,
                'article_date': article_date,
                'content_lower': content_lower
            })
        
        # If no candidates match required terms, return empty (will trigger "not enough data" message)
        if not candidates:
            return []
        
        # Extract keywords from query for keyword matching boost
        query_words = set(re.findall(r'\b[a-z]{3,}\b', query_lower))
        # Remove common stop words
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'they', 'this', 'that', 'with', 'from', 'what', 'about', 'which', 'when', 'there', 'their', 'will', 'each', 'make', 'how', 'like', 'just', 'over', 'such', 'into', 'than', 'them', 'then', 'now', 'news', 'latest', 'recent', 'today', 'tell', 'give', 'show'}
        query_keywords = query_words - stop_words
        
        # Second pass: build results with keyword boost
        for cand in candidates:
            row = cand['row']
            score = cand['score']
            content_lower = cand['content_lower']
            
            # Keyword boost: +5% for each query keyword found in article (max 20%)
            keyword_matches = sum(1 for kw in query_keywords if kw in content_lower)
            keyword_boost = min(0.20, keyword_matches * 0.05)
            
            # Only the most recent article gets the 10% recency boost
            recency_boost = 0.10 if cand['idx'] == most_recent_idx else 0
            
            boosted_score = min(1.0, score + recency_boost + keyword_boost)
            
            results.append({
                'title': str(row.get('title', '')),
                'content': str(row.get('content', '')),
                'date': str(row.get('date', ''))[:10],
                'source': str(row.get('source', '')),
                'link': str(row.get('link', '')),
                'score': boosted_score,
                'original_score': score,  # Raw semantic score
                'recency_boost': recency_boost,
                'keyword_boost': keyword_boost
            })
        
        # Sort by boosted score and return top_k
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def classify_query(self, query):
        """Classify query into category"""
        if not self.classifier:
            return {'category': 'general', 'confidence': 0.5}
        
        try:
            query_embedding = self.model.encode([query])
            proba = self.classifier.predict_proba(query_embedding)[0]
            pred_idx = np.argmax(proba)
            confidence = float(proba[pred_idx])
            
            # Handle both old and new format
            if self.label_encoder:
                category = self.label_encoder.inverse_transform([pred_idx])[0]
            elif hasattr(self, 'idx_to_label') and self.idx_to_label:
                category = self.idx_to_label.get(pred_idx, 'general')
            else:
                category = 'general'
            
            return {'category': category, 'confidence': confidence}
        except Exception as e:
            return {'category': 'general', 'confidence': 0.5}
    
    def get_direct_answer(self, query, content):
        """Extract direct answer from content"""
        if not content:
            return None
        
        query_lower = query.lower()
        sentences = re.split(r'[.!?]+', content)
        
        # Keywords to look for
        keywords = query_lower.split()
        keywords = [w for w in keywords if len(w) > 3]
        
        best_sentence = None
        best_score = 0
        
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 20:
                continue
            
            sent_lower = sent.lower()
            score = sum(1 for kw in keywords if kw in sent_lower)
            
            # Boost for numbers (prices, percentages)
            if re.search(r'\$[\d,.]+|\d+%|\d+\s*(million|billion|barrel|bpd)', sent_lower):
                score += 2
            
            if score > best_score:
                best_score = score
                best_sentence = sent
        
        return best_sentence
    
    def get_best_sentence(self, content, query):
        """Get the most relevant sentence"""
        return self.get_direct_answer(query, content)
    
    def extract_key_facts(self, content, query, max_facts=3):
        """Extract key facts from content"""
        if not content:
            return []
        
        facts = []
        # Better sentence splitting: don't split on periods in numbers (e.g., 1.4 million)
        # Split on period/!/? followed by space and capital letter or end of string
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', content)
        
        seen = set()  # Avoid duplicate facts
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 30 or len(sent) > 300:  # Allow longer sentences
                continue
            
            # Skip if we've seen similar content
            sent_key = sent[:50].lower()
            if sent_key in seen:
                continue
            seen.add(sent_key)
            
            # Look for factual patterns
            if re.search(r'\$[\d,.]+|\d+%|\d+\.?\d*\s*(million|billion|barrel|bpd|mcf)', sent, re.I):
                facts.append(sent)
            elif re.search(r'(announced|reported|said|increased|decreased|plans|will)', sent, re.I):
                facts.append(sent)
            
            if len(facts) >= max_facts:
                break
        
        return facts[:max_facts]
    
    def chat(self):
        """Interactive chat mode"""
        self.load_models()
        
        print("\n" + "=" * 60)
        print("  Oil & Gas News Chatbot")
        print("  Type 'quit' to exit")
        print("=" * 60)
        
        while True:
            try:
                query = input("\nYou: ").strip()
                
                if not query:
                    continue
                
                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                # Search
                results = self.search_articles(query, top_k=3)
                
                if not results:
                    print("\nBot: I don't have information about that topic.")
                    continue
                
                # Get classification
                classification = self.classify_query(query)
                print(f"\nTopic: {classification['category']} ({classification['confidence']:.0%})")
                
                # Show top result
                top = results[0]
                print(f"\nBot: Based on recent news from {top['source']}:")
                
                # Get answer
                answer = self.get_direct_answer(query, top['content'])
                if answer:
                    print(f"\n{answer}")
                
                print(f"\nRelevance: {top['score']:.0%} | Date: {top['date']}")
                
                # Show more results
                if len(results) > 1:
                    print("\nRelated articles:")
                    for r in results[1:3]:
                        print(f"  - {r['source']} ({r['date']}): {r['score']:.0%}")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}")


if __name__ == '__main__':
    bot = OilGasChatbot()
    bot.chat()
