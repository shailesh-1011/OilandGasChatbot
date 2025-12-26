# 🛢️ Oil & Gas News Chatbot

An AI-powered chatbot that scrapes, analyzes, and provides intelligent search over oil & gas industry news from 12+ global sources.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![ML](https://img.shields.io/badge/ML-Sentence_Transformers-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🌟 Features

- **🔍 Semantic Search**: Uses sentence-transformers for intelligent article matching
- **📰 Multi-Source Scraping**: Collects news from 12+ industry sources
- **🤖 NLP Classification**: Automatically categorizes articles by topic
- **📊 Named Entity Recognition**: Extracts companies, locations, and key entities
- **🎯 Direct Answers**: Provides concise answers to queries from article content
- **⏰ Automated Updates**: Daily scraping with cron job support
- **🌐 Clean Web UI**: Google-like search interface

## 📸 Demo

```
┌─────────────────────────────────────────────────────────────┐
│  🛢️ Oil & Gas News Chatbot                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│              Oil&Gas Search                                 │
│                                                             │
│   ┌─────────────────────────────────────────────┐           │
│   │ What is the latest OPEC decision?     🔍   │           │
│   └─────────────────────────────────────────────┘           │
│                                                             │
│   📌 Topic: REGULATION (85%)                                │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ 📄 OPEC+ Maintains Production Cuts                  │   │
│   │ Reuters • December 25, 2025 • 92% match             │   │
│   │                                                     │   │
│   │ 💡 DIRECT ANSWER                                    │   │
│   │ OPEC+ agreed to extend production cuts through Q1   │   │
│   │ 2026, keeping output reduced by 2.2 million bpd.    │   │
│   │                                                     │   │
│   │ 📋 Key Facts:                                       │   │
│   │ • Production cuts extended through Q1 2026          │   │
│   │ • 2.2 million barrels per day reduction maintained  │   │
│   │ • Saudi Arabia leads voluntary cuts                 │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🏗️ Architecture

```
oilandgasChatBot/
├── main.py                 # Main orchestrator - runs scrapers & training
├── scheduler.py            # Automated scheduling (10 AM & 5 PM daily)
├── setup_vps.sh           # One-command VPS deployment script
│
├── scrapers/              # News scrapers (12 sources)
│   ├── rigzone.py
│   ├── reuters.py
│   ├── oilprice.py
│   ├── worldoil.py
│   ├── offshore_energy.py
│   ├── energynow.py
│   ├── boereport.py
│   ├── ogj.py
│   ├── indianoilandgas.py
│   ├── energy_economictimes_indiatimes.py
│   ├── news_oilandgaswatch.py
│   ├── reuters_climate.py
│   ├── utils.py           # Shared utilities
│   └── articles.csv       # Scraped articles database
│
├── ml/                    # Machine Learning models
│   ├── chatbot.py         # Main chatbot class with search
│   ├── semantic_embeddings.py  # Sentence-transformer embeddings
│   ├── text_classifier.py # Topic classification
│   ├── topic_clustering.py # Unsupervised clustering
│   ├── ner_extraction.py  # Named Entity Recognition
│   ├── train_all.py       # Training pipeline
│   ├── evaluate.py        # Model evaluation
│   └── *.pkl / *.json     # Trained model files
│
└── web/                   # Flask web application
    ├── app.py             # Flask routes & API
    └── templates/
        └── index.html     # Search UI
```

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone the repository
git clone https://github.com/shailesh-1011/OilandGasChatbot.git
cd OilandGasChatbot

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 4. Run everything (scrape + train + web server)
python main.py --run
```

Then open **http://localhost:5000** in your browser.

### Command Line Options

```bash
python main.py              # Run scrapers only
python main.py --train      # Scrape + train ML models
python main.py --run        # Scrape + train + start web server
python main.py --web        # Start web server only (uses existing models)
```

## 🖥️ VPS Deployment

### One-Command Setup

```bash
# On your VPS (Ubuntu 22.04)
bash setup_vps.sh
```

This script automatically:
- ✅ Updates system packages
- ✅ Installs Python, Nginx
- ✅ Creates virtual environment
- ✅ Installs all dependencies
- ✅ Sets up systemd service (auto-start)
- ✅ Configures Nginx reverse proxy
- ✅ Sets up daily cron job (6 AM)

### Manual Deployment

```bash
# 1. Install dependencies
apt update && apt install -y python3 python3-pip python3-venv nginx

# 2. Setup project
cd /root/oilandgasChatBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Initial scrape & train
python main.py --train

# 4. Start with Gunicorn
gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 web.app:app
```

### Service Management

```bash
# Check status
systemctl status oilgas-api

# View logs
journalctl -u oilgas-api -f

# Restart service
systemctl restart oilgas-api

# Manual scrape
cd /root/oilandgasChatBot && source venv/bin/activate && python scheduler.py --once
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web search interface |
| `/search` | POST | Search (form data) |
| `/api/search` | POST | Search (JSON API) |
| `/api/stats` | GET | Article statistics |
| `/api/health` | GET | Health check |

### API Examples

**Search Request:**
```bash
curl -X POST http://your-server/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "oil price forecast"}'
```

**Response:**
```json
{
  "success": true,
  "query": "oil price forecast",
  "topic": "price_market",
  "topic_confidence": "85%",
  "results": [
    {
      "title": "Brent Crude Falls Amid Market Uncertainty",
      "source": "Reuters",
      "date": "2025-12-25",
      "relevance": "92.5%",
      "direct_answer": "Oil prices are expected to...",
      "key_facts": ["Brent at $73.50", "WTI at $69.80"]
    }
  ]
}
```

## 📰 News Sources

| Source | Type | Coverage |
|--------|------|----------|
| [Rigzone](https://www.rigzone.com) | Industry News | Global |
| [Reuters Energy](https://www.reuters.com/business/energy/) | Wire Service | Global |
| [OilPrice.com](https://oilprice.com) | Market Analysis | Global |
| [World Oil](https://www.worldoil.com) | Industry Magazine | Global |
| [Offshore Energy](https://www.offshore-energy.biz) | Offshore Focus | Global |
| [Energy Now](https://energynow.com) | North America | US/Canada |
| [BOE Report](https://boereport.com) | Canada Focus | Canada |
| [OGJ](https://www.ogj.com) | Industry Journal | Global |
| [Indian Oil & Gas](https://www.indianoilandgas.com) | India Focus | India |
| [ET Energy](https://energy.economictimes.indiatimes.com) | India News | India |
| [Oil & Gas Watch](https://news.oilandgaswatch.org) | Environmental | US |
| [Reuters Climate](https://www.reuters.com/sustainability/) | Climate/ESG | Global |

## 🧠 ML Pipeline

### 1. Semantic Embeddings
- **Model**: `all-mpnet-base-v2` (Sentence Transformers)
- **Purpose**: Convert articles to 768-dim vectors for similarity search

### 2. Text Classification
- **Model**: Logistic Regression on embeddings
- **Categories**: 
  - `price_market` - Oil prices, trading, forecasts
  - `production` - Drilling, output, reserves
  - `pipeline_lng` - Infrastructure, LNG, transport
  - `corporate` - M&A, earnings, company news
  - `geopolitics` - OPEC, sanctions, conflicts
  - `regulation` - Policies, laws, permits
  - `exploration` - Discoveries, surveys
  - `other` - Miscellaneous

### 3. Topic Clustering
- **Model**: K-Means (10 clusters)
- **Purpose**: Unsupervised article grouping

### 4. Named Entity Recognition
- **Model**: spaCy `en_core_web_sm`
- **Entities**: Organizations, Locations, Monetary values

## 📋 Requirements

```
flask==3.0.0
flask-cors==4.0.0
gunicorn==21.2.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
pandas>=2.0.0
numpy>=1.24.0
sentence-transformers>=2.2.0
scikit-learn>=1.3.0
spacy>=3.7.0
schedule>=1.2.0
```

## 🔧 Configuration

### Environment Variables (Optional)

```bash
export FLASK_ENV=production
export FLASK_DEBUG=0
export PORT=5000
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

## 📊 Performance

- **Scraping**: ~80 seconds for all 12 sources
- **Training**: ~5-10 minutes (depends on article count)
- **Search**: <500ms response time
- **Memory**: ~2GB with loaded models

## 🛣️ Roadmap

- [ ] Add more news sources
- [ ] Implement article summarization
- [ ] Add sentiment analysis
- [ ] Create mobile-responsive UI
- [ ] Add user query history
- [ ] Implement caching layer
- [ ] Add Docker support

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Shailesh**
- GitHub: [@shailesh-1011](https://github.com/shailesh-1011)

## 🙏 Acknowledgments

- [Sentence Transformers](https://www.sbert.net/) for semantic embeddings
- [spaCy](https://spacy.io/) for NLP
- [Flask](https://flask.palletsprojects.com/) for web framework
- All the news sources for their valuable content

---

⭐ **Star this repo if you find it useful!**
