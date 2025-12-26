"""
Master Training Script - Runs all ML training steps
Supports --force flag to retrain even if no new articles
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(force=False):
    """Run all training steps"""
    print("=" * 60)
    print("  ML TRAINING PIPELINE")
    if force:
        print("  (FORCE MODE - retraining all)")
    print("=" * 60)
    
    # Step 1: Create embeddings
    print("\n" + "-" * 60)
    print("  STEP 1: Creating Semantic Embeddings")
    print("-" * 60)
    try:
        from ml.semantic_embeddings import create_embeddings
        create_embeddings()
    except Exception as e:
        print(f"Error in embeddings: {e}")
    
    # Step 2: Train classifier
    print("\n" + "-" * 60)
    print("  STEP 2: Training Text Classifier")
    print("-" * 60)
    try:
        from ml.text_classifier import train_classifier
        train_classifier(force=force)
    except Exception as e:
        print(f"Error in classifier: {e}")
    
    # Step 3: Create clusters
    print("\n" + "-" * 60)
    print("  STEP 3: Creating Topic Clusters")
    print("-" * 60)
    try:
        from ml.topic_clustering import create_clusters
        create_clusters(force=force)
    except Exception as e:
        print(f"Error in clustering: {e}")
    
    # Step 4: Extract entities
    print("\n" + "-" * 60)
    print("  STEP 4: Extracting Named Entities")
    print("-" * 60)
    try:
        from ml.ner_extraction import extract_all_entities
        extract_all_entities()
    except Exception as e:
        print(f"Error in NER: {e}")
    
    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE!")
    print("=" * 60)


if __name__ == '__main__':
    force = '--force' in sys.argv
    main(force=force)
