"""
Main Runner for Oil & Gas News Scrapers
Runs all scrapers in the scrapers folder and provides a summary
"""

import os
import sys
import importlib.util
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


# List of scraper modules to run (in order)
SCRAPERS = [
    'rigzone',
    'news_oilandgaswatch',
    'ogj',
    'oilprice',
    'boereport',
    'energynow',
    'energy_economictimes_indiatimes',
    'indianoilandgas',
    'offshore_energy',
    'reuters',
    'reuters_climate',
    'worldoil',
]

# Scrapers folder path
SCRAPERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scrapers')


def load_and_run_scraper(scraper_name):
    """
    Dynamically load and run a scraper module
    Returns: (success: bool, articles_count: int, error_msg: str or None, articles: list)
    """
    try:
        # Build path to scraper file
        scraper_path = os.path.join(SCRAPERS_DIR, f'{scraper_name}.py')
        
        if not os.path.exists(scraper_path):
            return False, 0, f"File not found: {scraper_path}", []
        
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(scraper_name, scraper_path)
        module = importlib.util.module_from_spec(spec)
        
        # Add scrapers dir to path temporarily for imports
        if SCRAPERS_DIR not in sys.path:
            sys.path.insert(0, SCRAPERS_DIR)
        
        spec.loader.exec_module(module)
        
        # Try different function names used by scrapers
        # Most use scrape(), some use main(), worldoil uses scrape_news()
        articles = []
        if hasattr(module, 'scrape_news'):
            result = module.scrape_news()
            if isinstance(result, list):
                articles = result
                count = len(result)
            else:
                count = result if isinstance(result, int) else 0
        elif hasattr(module, 'scrape'):
            result = module.scrape()
            if isinstance(result, list):
                articles = result
                count = len(result)
            else:
                count = result if isinstance(result, int) else 0
        elif hasattr(module, 'main'):
            result = module.main()
            if isinstance(result, list):
                articles = result
                count = len(result)
            else:
                count = result if isinstance(result, int) else 0
        else:
            return False, 0, "No scrape(), scrape_news(), or main() function found", []
        
        # Save articles if we got any and the module has save_articles function
        if articles and hasattr(module, 'save_articles'):
            module.save_articles(articles)
            
        return True, count, None, articles
            
    except Exception as e:
        return False, 0, str(e), []


def run_all_scrapers():
    """Run all scrapers and display summary"""
    print("=" * 70)
    print(f"  OIL & GAS NEWS SCRAPER - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print(f"\nRunning {len(SCRAPERS)} scrapers...\n")
    

    results = []
    total_articles = 0
    start_time = time.time()
    
    for i, scraper_name in enumerate(SCRAPERS, 1):
        print(f"\n{'-' * 70}")
        print(f"[{i}/{len(SCRAPERS)}] Running: {scraper_name}")
        print("-" * 70)
        
        scraper_start = time.time()
        success, count, error, articles = load_and_run_scraper(scraper_name)
        scraper_time = time.time() - scraper_start
        
        if success:
            results.append({
                'name': scraper_name,
                'status': '[OK]',
                'articles': count,
                'time': scraper_time,
                'error': None
            })
            total_articles += count
        else:
            results.append({
                'name': scraper_name,
                'status': '[FAIL]',
                'articles': 0,
                'time': scraper_time,
                'error': error
            })
            print(f"\n  ERROR: {error}")
    
    total_time = time.time() - start_time
    
    # Print summary
    print("\n")
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"\n{'Scraper':<35} {'Status':<8} {'Articles':<10} {'Time':<10}")
    print("-" * 70)
    
    for r in results:
        status_str = f"{r['status']}"
        time_str = f"{r['time']:.1f}s"
        print(f"{r['name']:<35} {status_str:<8} {r['articles']:<10} {time_str:<10}")
    
    print("-" * 70)
    successful = sum(1 for r in results if r['status'] == '[OK]')
    failed = len(results) - successful
    
    print(f"\n[OK] Completed: {successful}/{len(SCRAPERS)} scrapers")
    if failed > 0:
        print(f"[FAIL] Failed: {failed} scrapers")
    print(f"Total new articles: {total_articles}")
    print(f"Total time: {total_time:.1f} seconds")
    
    # Show failed scrapers details
    failed_scrapers = [r for r in results if r['status'] == '[FAIL]']
    if failed_scrapers:
        print("\n[WARNING] Failed scrapers:")
        for r in failed_scrapers:
            print(f"  - {r['name']}: {r['error'][:60]}...")
    
    print("\n" + "=" * 70)
    
    return results


def run_all_scrapers_parallel(max_workers=4):
    """Run all scrapers in parallel for faster execution"""
    print("=" * 70)
    print(f"  OIL & GAS NEWS SCRAPER (FAST MODE) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print(f"\nRunning {len(SCRAPERS)} scrapers in parallel (max {max_workers} at a time)...\n")
    
    results = []
    total_articles = 0
    start_time = time.time()
    
    def scrape_wrapper(scraper_name):
        scraper_start = time.time()
        success, count, error, articles = load_and_run_scraper(scraper_name)
        scraper_time = time.time() - scraper_start
        return {
            'name': scraper_name,
            'status': '[OK]' if success else '[FAIL]',
            'articles': count,
            'time': scraper_time,
            'error': error
        }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_wrapper, name): name for name in SCRAPERS}
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result['status'] == '[OK]':
                total_articles += result['articles']
                print(f"  [OK] {result['name']}: {result['articles']} articles ({result['time']:.1f}s)")
            else:
                print(f"  [FAIL] {result['name']}: {result['error'][:40]}...")
    
    total_time = time.time() - start_time
    
    # Print summary
    print("\n")
    print("=" * 70)
    print("  SUMMARY (FAST MODE)")
    print("=" * 70)
    print(f"\n{'Scraper':<35} {'Status':<8} {'Articles':<10} {'Time':<10}")
    print("-" * 70)
    
    # Sort by name for consistent display
    results.sort(key=lambda x: SCRAPERS.index(x['name']))
    
    for r in results:
        time_str = f"{r['time']:.1f}s"
        print(f"{r['name']:<35} {r['status']:<8} {r['articles']:<10} {time_str:<10}")
    
    print("-" * 70)
    successful = sum(1 for r in results if r['status'] == '[OK]')
    failed = len(results) - successful
    
    print(f"\n[OK] Completed: {successful}/{len(SCRAPERS)} scrapers")
    if failed > 0:
        print(f"[FAIL] Failed: {failed} scrapers")
    print(f"Total new articles: {total_articles}")
    print(f"Total time: {total_time:.1f} seconds (vs ~{total_time * max_workers:.0f}s sequential)")
    
    print("\n" + "=" * 70)
    
    return results


def run_single_scraper(scraper_name):
    """Run a single scraper by name"""
    if scraper_name not in SCRAPERS:
        print(f"Unknown scraper: {scraper_name}")
        print(f"Available scrapers: {', '.join(SCRAPERS)}")
        return
    
    print(f"Running single scraper: {scraper_name}")
    success, count, error, articles = load_and_run_scraper(scraper_name)
    
    if success:
        print(f"\n[OK] {scraper_name}: {count} articles scraped and saved")
    else:
        print(f"\n[FAIL] {scraper_name}: {error}")


def list_scrapers():
    """List all available scrapers"""
    print("\nAvailable scrapers:")
    print("-" * 40)
    for i, name in enumerate(SCRAPERS, 1):
        scraper_path = os.path.join(SCRAPERS_DIR, f'{name}.py')
        exists = "[OK]" if os.path.exists(scraper_path) else "[MISSING]"
        print(f"  {i:2}. {exists} {name}")
    print("-" * 40)
    print(f"Total: {len(SCRAPERS)} scrapers")


def run_training():
    """Run ML training pipeline"""
    print("\n" + "=" * 70)
    print("  STARTING ML TRAINING PIPELINE")
    print("=" * 70)
    
    try:
        from ml.train_all import main as train_main
        train_main()
        return True
    except Exception as e:
        print(f"\n[FAIL] Training failed: {e}")
        return False


def run_evaluation():
    """Run model evaluation"""
    print("\n" + "=" * 70)
    print("  RUNNING MODEL EVALUATION")
    print("=" * 70)
    
    try:
        from ml.evaluate import full_evaluation
        results = full_evaluation()
        return results
    except Exception as e:
        print(f"\n[FAIL] Evaluation failed: {e}")
        return None


def run_full_pipeline():
    """
    Full automation: Scrape → Train → Evaluate
    """
    print("=" * 70)
    print("  FULL PIPELINE: SCRAPE → TRAIN → EVALUATE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    # Step 1: Scrape
    print("\n" + "─" * 70)
    print("  STEP 1/3: SCRAPING NEWS ARTICLES")
    print("─" * 70)
    scrape_results = run_all_scrapers()
    
    total_articles = sum(r['articles'] for r in scrape_results)
    
    if total_articles == 0:
        print("\n[INFO] No new articles scraped. Checking if training data exists...")
    
    # Step 2: Train
    print("\n" + "─" * 70)
    print("  STEP 2/3: TRAINING ML MODELS")
    print("─" * 70)
    training_success = run_training()
    
    if not training_success:
        print("\n[ERROR] Pipeline stopped due to training failure")
        return False
    
    # Step 3: Evaluate
    print("\n" + "─" * 70)
    print("  STEP 3/3: EVALUATING MODELS")
    print("─" * 70)
    eval_results = run_evaluation()
    
    # Final Summary
    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETE!")
    print("=" * 70)
    print(f"\n  New articles scraped: {total_articles}")
    
    if eval_results and 'classifier' in eval_results:
        acc = eval_results['classifier']['accuracy']
        print(f"  Classifier accuracy: {acc:.2%}")
    
    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    return True


def run_web_server(host='0.0.0.0', port=5000):
    """Start the Flask web server"""
    print("\n" + "=" * 70)
    print("  STARTING WEB SERVER")
    print("=" * 70)
    print(f"\n  Open http://localhost:{port} in your browser")
    print("  Press Ctrl+C to stop\n")
    
    try:
        from web.app import app
        app.run(debug=False, host=host, port=port)
    except Exception as e:
        print(f"\n[ERROR] Web server failed: {e}")


def run_chatbot():
    """Start the terminal chatbot"""
    print("\n" + "=" * 70)
    print("  STARTING CHATBOT")
    print("=" * 70)
    
    try:
        from ml.chatbot import OilGasChatbot
        chatbot = OilGasChatbot()
        chatbot.chat()
    except Exception as e:
        print(f"\n[ERROR] Chatbot failed: {e}")


def run_everything(fast=True):
    """
    MASTER FUNCTION: Scrape → Train → Start Web UI
    This is the one-click solution to run everything
    """
    print("=" * 70)
    print("  OIL & GAS NEWS INTELLIGENCE - FULL SYSTEM")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    # Step 1: Scrape all news (parallel by default for speed)
    print("\n" + "=" * 70)
    print("  STEP 1/3: SCRAPING NEWS ARTICLES" + (" (FAST MODE)" if fast else ""))
    print("=" * 70)
    if fast:
        scrape_results = run_all_scrapers_parallel()
    else:
        scrape_results = run_all_scrapers()
    total_articles = sum(r['articles'] for r in scrape_results)
    
    # Step 2: Train models
    print("\n" + "=" * 70)
    print("  STEP 2/3: TRAINING ML MODELS")
    print("=" * 70)
    run_training()
    
    # Step 3: Start web server
    print("\n" + "=" * 70)
    print("  STEP 3/3: STARTING WEB SERVER")
    print("=" * 70)
    print(f"\n  Total articles: {total_articles}")
    print("  Web UI starting at: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    
    run_web_server()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Oil & Gas News Intelligence System')
    parser.add_argument('--list', '-l', action='store_true', help='List all available scrapers')
    parser.add_argument('--scraper', '-s', type=str, help='Run a specific scraper by name')
    parser.add_argument('--all', '-a', action='store_true', help='Run all scrapers only')
    parser.add_argument('--fast', '-f', action='store_true', help='Run scrapers in parallel (4x faster)')
    parser.add_argument('--train', '-t', action='store_true', help='Run ML training after scraping')
    parser.add_argument('--evaluate', '-e', action='store_true', help='Evaluate trained models')
    parser.add_argument('--pipeline', '-p', action='store_true', help='Full pipeline: scrape + train + evaluate')
    parser.add_argument('--web', '-w', action='store_true', help='Start web server only')
    parser.add_argument('--chat', '-c', action='store_true', help='Start terminal chatbot')
    parser.add_argument('--run', '-r', action='store_true', help='RUN EVERYTHING: scrape + train + web UI')
    parser.add_argument('--port', type=int, default=5000, help='Port for web server (default: 5000)')
    
    args = parser.parse_args()
    
    if args.list:
        list_scrapers()
    elif args.scraper:
        run_single_scraper(args.scraper)
    elif args.evaluate:
        run_evaluation()
    elif args.train:
        if args.fast:
            run_all_scrapers_parallel()
        else:
            run_all_scrapers()
        run_training()
    elif args.pipeline:
        run_full_pipeline()
    elif args.web:
        run_web_server(port=args.port)
    elif args.chat:
        run_chatbot()
    elif args.run:
        run_everything()
    elif args.all:
        if args.fast:
            run_all_scrapers_parallel()
        else:
            run_all_scrapers()
    elif args.fast:
        # Just --fast by itself runs parallel scrapers
        run_all_scrapers_parallel()
    else:
        # Default: show help
        print("=" * 70)
        print("  OIL & GAS NEWS INTELLIGENCE SYSTEM")
        print("=" * 70)
        print("\nUsage:")
        print("  python main.py --run        # RUN EVERYTHING (scrape + train + web)")
        print("  python main.py --fast       # Scrape in parallel (4x faster)")
        print("  python main.py --web        # Start web UI only")
        print("  python main.py --chat       # Start terminal chatbot")
        print("  python main.py --all        # Scrape articles only")
        print("  python main.py --train      # Scrape + train models")
        print("  python main.py --pipeline   # Scrape + train + evaluate")
        print("  python main.py --list       # List all scrapers")
        print("\nFor deployment:")
        print("  python scheduler.py         # Scheduled scraping (10 AM & 5 PM)")
        print("\n" + "=" * 70)
