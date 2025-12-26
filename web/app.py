"""
Oil & Gas News Search - Web Application
Clean Google-like interface for searching oil & gas news
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ml.chatbot import OilGasChatbot

app = Flask(__name__)

# Enable CORS for API access from external applications
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize chatbot (loaded once)
chatbot = None

def get_chatbot():
    global chatbot
    if chatbot is None:
        chatbot = OilGasChatbot()
        chatbot.load_models()
    return chatbot


@app.route('/')
def home():
    """Render the main search page"""
    return render_template('index.html')


@app.route('/search', methods=['POST'])
def search():
    """Handle search queries"""
    query = request.form.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Please enter a search query'})
    
    try:
        bot = get_chatbot()
        
        # Ensure models are loaded
        if not bot.loaded:
            bot.load_models()
        
        # Get classification
        classification = bot.classify_query(query)
        
        # Search for articles (get more to filter)
        results = bot.search_articles(query, top_k=10)
        
        # If no results (query required specific terms that weren't found)
        if not results:
            return jsonify({
                'success': False,
                'message': "I couldn't find relevant articles for this query in my database. Try searching for topics like oil prices, OPEC, drilling, offshore, or natural gas.",
                'topic': classification['category'] if classification else None
            })
        
        # Filter by relevance >= 35% (semantic score)
        relevant_results = []
        for r in results:
            if r.get('original_score', 0) >= 0.35:
                relevant_results.append(r)
        
        if not relevant_results:
            return jsonify({
                'success': False,
                'message': "I couldn't find highly relevant articles for this query. Try being more specific or search for related oil & gas topics.",
                'topic': classification['category'] if classification else None
            })
        
        # Results are already sorted by boosted score (recent articles get 10% boost)
        # Get top 2 results
        top_results = relevant_results[:2]
        # Format results
        formatted_results = []
        for result in top_results:
            content = result['content']
            
            # Get direct answer
            direct = bot.get_direct_answer(query, content)
            if direct:
                direct = direct.replace('**', '').replace('*', '')
            
            # Get best sentence
            best_sent = bot.get_best_sentence(content, query)
            
            # Extract key facts (already clean, no emojis)
            facts = bot.extract_key_facts(content, query)
            
            # Check if article has recency boost
            recency_boost = result.get('recency_boost', 0)
            keyword_boost = result.get('keyword_boost', 0)
            is_recent = recency_boost > 0
            original_score = result.get('original_score', result['score'])
            boosted_score = result['score']  # This is the actual sorting score
            
            formatted_results.append({
                'source': result['source'],
                'date': result['date'],
                'relevance': f"{boosted_score:.0%}",  # Show boosted score (what we sort by)
                'is_recent': is_recent,  # Separate flag for recency
                'recency_boost': f"+{recency_boost:.0%}" if recency_boost > 0 else None,
                'keyword_boost': f"+{keyword_boost:.0%}" if keyword_boost > 0 else None,
                'direct_answer': direct,
                'summary': best_sent,
                'facts': facts,
                'link': result.get('link', '')
            })
        
        return jsonify({
            'success': True,
            'topic': classification['category'] if classification else None,
            'topic_confidence': f"{classification['confidence']:.0%}" if classification else None,
            'results': formatted_results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/stats')
def stats():
    """Get database statistics"""
    try:
        bot = get_chatbot()
        
        sources = bot.articles['source'].value_counts().to_dict()
        total = len(bot.articles)
        
        return jsonify({
            'total_articles': total,
            'sources': sources
        })
    except Exception as e:
        return jsonify({'error': str(e)})


# ============================================
# API ENDPOINTS FOR EXTERNAL FRONTENDS (ODOO)
# ============================================

@app.route('/api/search', methods=['POST', 'OPTIONS'])
def api_search():
    """
    API endpoint for external frontends (Odoo, etc.)
    Accepts JSON body: {"query": "your search query"}
    Returns JSON response with search results
    """
    # Handle preflight CORS request
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'})
    
    # Accept both JSON and form data
    if request.is_json:
        data = request.get_json()
        query = data.get('query', '').strip()
    else:
        query = request.form.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Please provide a query parameter'})
    
    try:
        bot = get_chatbot()
        
        if not bot.loaded:
            bot.load_models()
        
        classification = bot.classify_query(query)
        results = bot.search_articles(query, top_k=10)
        
        if not results:
            return jsonify({
                'success': False,
                'message': "No relevant articles found for this query.",
                'topic': classification['category'] if classification else None
            })
        
        # Filter by relevance >= 35%
        relevant_results = [r for r in results if r.get('original_score', 0) >= 0.35]
        
        if not relevant_results:
            return jsonify({
                'success': False,
                'message': "No highly relevant articles found. Try a different query.",
                'topic': classification['category'] if classification else None
            })
        
        top_results = relevant_results[:2]
        formatted_results = []
        
        for result in top_results:
            content = result['content']
            direct = bot.get_direct_answer(query, content)
            if direct:
                direct = direct.replace('**', '').replace('*', '')
            
            best_sent = bot.get_best_sentence(content, query)
            facts = bot.extract_key_facts(content, query)
            
            formatted_results.append({
                'title': result['title'],
                'source': result['source'],
                'date': result['date'],
                'url': result.get('url', ''),
                'relevance': f"{result.get('original_score', result['score'])*100:.1f}%",
                'direct_answer': direct,
                'key_sentence': best_sent,
                'key_facts': facts,
                'snippet': content[:300] + '...' if len(content) > 300 else content
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'topic': classification['category'] if classification else None,
            'topic_confidence': f"{classification['confidence']*100:.0f}%" if classification else None,
            'results': formatted_results,
            'total_found': len(relevant_results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """API endpoint to get database statistics"""
    try:
        bot = get_chatbot()
        sources = bot.articles['source'].value_counts().to_dict()
        total = len(bot.articles)
        
        return jsonify({
            'success': True,
            'total_articles': total,
            'sources': sources
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'oil-gas-chatbot'})

if __name__ == '__main__':
    print("Starting Oil & Gas News Search...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
