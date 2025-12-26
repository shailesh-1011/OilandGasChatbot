"""
Scheduled Scraper - Runs at 10 AM and 5 PM daily
For deployment on free servers (Railway, Render, PythonAnywhere, etc.)
"""

import os
import sys
import time
import schedule
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def run_scraping():
    """Run all scrapers and update models"""
    print(f"\n{'='*60}")
    print(f"  SCHEDULED SCRAPING - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    try:
        # Import and run main scraper
        from main import main as run_scrapers
        run_scrapers()
        
        print("\n[OK] Scraping completed successfully!")
        
        # Retrain embeddings with new data
        print("\n[INFO] Updating embeddings with new articles...")
        from ml.semantic_embeddings import create_embeddings
        create_embeddings()
        
        print("\n[OK] Models updated with new data!")
        
    except Exception as e:
        print(f"\n[ERROR] Scraping failed: {e}")


def run_scheduler():
    """Run the scheduler for 10 AM and 5 PM daily"""
    print("="*60)
    print("  OIL & GAS NEWS SCHEDULER")
    print("="*60)
    print("\nScheduled scraping times:")
    print("  - 10:00 AM daily")
    print("  - 5:00 PM daily")
    print("\nPress Ctrl+C to stop\n")
    
    # Schedule jobs
    schedule.every().day.at("10:00").do(run_scraping)
    schedule.every().day.at("17:00").do(run_scraping)
    
    # Run initial scrape on startup
    print("[INFO] Running initial scrape on startup...")
    run_scraping()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == '__main__':
    # Check if we should run once or as scheduler
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        run_scraping()
    else:
        run_scheduler()
