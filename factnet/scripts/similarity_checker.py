"""
Similarity Checker Module for FactNet

This module provides functionality to compare a submitted news article with 
existing trusted articles to determine factual accuracy.

Usage directly:
    python similarity_checker.py --text "Article text to check"
    
Or import as a module:
    from similarity_checker import check_article_similarity
"""

import os
import sys
import logging
import argparse
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Import sentence-transformers
from sentence_transformers import SentenceTransformer, util

# Import NLTK for text segmentation
import nltk
from nltk.tokenize import sent_tokenize

# Import MongoDB client
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("similarity_checker.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Download required NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')


class SimilarityChecker:
    """A class for checking similarity between articles to determine factual accuracy."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the similarity checker with the specified model.
        
        Args:
            model_name: Name of the sentence-transformers model to use
        """
        logger.info(f"Initializing SimilarityChecker with model: {model_name}")
        self.model = SentenceTransformer(model_name)
        
        # Set thresholds for similarity
        self.high_similarity_threshold = 0.75
        self.medium_similarity_threshold = 0.5
    
    def segment_text(self, text: str) -> List[str]:
        """
        Segment text into sentences or meaningful chunks.
        
        Args:
            text: Input text to segment
            
        Returns:
            List of text segments
        """
        if not text:
            return []
        
        # Use NLTK's sentence tokenizer
        sentences = sent_tokenize(text)
        
        # Filter out very short sentences (likely not meaningful)
        return [s for s in sentences if len(s.split()) > 3]
    
    def encode_text(self, text: str) -> Any:
        """
        Encode text into embeddings using the sentence-transformer model.
        
        Args:
            text: Input text
            
        Returns:
            Text embedding
        """
        return self.model.encode(text, convert_to_tensor=True)
    
    def compute_similarity(self, submitted_text: str, trusted_text: str) -> float:
        """
        Compute similarity between submitted and trusted text.
        
        Args:
            submitted_text: Submitted article text
            trusted_text: Trusted article text
            
        Returns:
            Similarity score (0-1)
        """
        if not submitted_text or not trusted_text:
            return 0.0
        
        # Encode texts
        submitted_embedding = self.encode_text(submitted_text)
        trusted_embedding = self.encode_text(trusted_text)
        
        # Compute cosine similarity
        similarity = util.pytorch_cos_sim(submitted_embedding, trusted_embedding)
        
        # Convert to float and return
        return float(similarity[0][0])
    
    def compute_segment_similarity(self, 
                                  submitted_segments: List[str], 
                                  trusted_segments: List[str]) -> float:
        """
        Compute similarity between segments of submitted and trusted articles.
        
        Args:
            submitted_segments: List of segments from submitted article
            trusted_segments: List of segments from trusted article
            
        Returns:
            Segment similarity score (0-1)
        """
        if not submitted_segments or not trusted_segments:
            return 0.0
        
        # Encode all segments
        submitted_embeddings = self.model.encode(submitted_segments, convert_to_tensor=True)
        trusted_embeddings = self.model.encode(trusted_segments, convert_to_tensor=True)
        
        # Compute cosine similarity matrix
        similarity_matrix = util.pytorch_cos_sim(submitted_embeddings, trusted_embeddings)
        
        # For each submitted segment, find the best matching trusted segment
        max_similarities = []
        
        for i in range(len(submitted_segments)):
            # Get the highest similarity for this segment
            max_sim = float(similarity_matrix[i].max())
            max_similarities.append(max_sim)
        
        # Return the average of the max similarities
        if max_similarities:
            return sum(max_similarities) / len(max_similarities)
        return 0.0
    
    def check_similarity(self, 
                         submitted_text: str, 
                         trusted_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Check similarity between a submitted article and a list of trusted articles.
        
        Args:
            submitted_text: Text of the submitted article
            trusted_articles: List of trusted articles (with 'content' and 'headline' fields)
            
        Returns:
            Dictionary with similarity results
        """
        if not submitted_text or not trusted_articles:
            return {
                "overall_similarity": 0.0,
                "similarity_percentage": "0.0%",
                "factual_accuracy": "Low",
                "matches": [],
            }
        
        # Segment the submitted text
        submitted_segments = self.segment_text(submitted_text)
        
        # Process each trusted article
        article_similarities = []
        
        for article in trusted_articles:
            # Combine headline and content
            trusted_text = f"{article.get('headline', '')} {article.get('content', '')}"
            
            # Compute overall document similarity
            doc_similarity = self.compute_similarity(submitted_text, trusted_text)
            
            # Compute segment-level similarity if document similarity is reasonable
            segment_similarity = 0.0
            if doc_similarity >= self.medium_similarity_threshold:
                trusted_segments = self.segment_text(trusted_text)
                segment_similarity = self.compute_segment_similarity(
                    submitted_segments, trusted_segments
                )
            
            # Calculate combined similarity (70% document, 30% segment)
            combined_similarity = 0.7 * doc_similarity + 0.3 * segment_similarity
            
            article_similarities.append({
                "article_id": str(article.get("_id")),
                "headline": article.get("headline", ""),
                "source": article.get("source", ""),
                "similarity": combined_similarity,
                "url": article.get("url", "")
            })
        
        # Sort by similarity and get the top 3
        article_similarities.sort(key=lambda x: x["similarity"], reverse=True)
        top_matches = article_similarities[:3]
        
        # Get the highest similarity score
        best_similarity = top_matches[0]["similarity"] if top_matches else 0.0
        
        # Determine factual accuracy level
        if best_similarity >= self.high_similarity_threshold:
            factual_accuracy = "High"
        elif best_similarity >= self.medium_similarity_threshold:
            factual_accuracy = "Medium"
        else:
            factual_accuracy = "Low"
        
        # Create result
        result = {
            "overall_similarity": best_similarity,
            "similarity_percentage": f"{best_similarity * 100:.1f}%",
            "factual_accuracy": factual_accuracy,
            "matches": top_matches,
        }
        
        return result


def check_article_similarity(article_text: str, mongo_uri: str = "mongodb://localhost:27017/") -> Dict[str, Any]:
    """
    Check the similarity of an article against trusted sources in the database.
    
    Args:
        article_text: Text to check
        mongo_uri: MongoDB connection URI
        
    Returns:
        Dictionary with similarity results
    """
    # Connect to MongoDB
    client = MongoClient(mongo_uri)
    db = client["factnet"]
    collection = db["articles"]
    
    # Get trusted articles from the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    trusted_articles = list(collection.find({
        "is_trusted": True,
        "published_date": {"$gte": thirty_days_ago}
    }).limit(20))
    
    # Initialize the similarity checker
    checker = SimilarityChecker()
    
    # Check similarity
    result = checker.check_similarity(article_text, trusted_articles)
    
    # Close MongoDB connection
    client.close()
    
    return result


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Check article similarity against trusted sources.')
    parser.add_argument('--text', required=True, help='Article text to check')
    parser.add_argument('--mongodb', dest='mongo_uri', default="mongodb://localhost:27017/",
                        help='MongoDB connection URI')
    
    args = parser.parse_args()
    
    try:
        # Check similarity
        result = check_article_similarity(args.text, args.mongo_uri)
        
        # Print results
        print(f"Similarity: {result['similarity_percentage']}")
        print(f"Factual Accuracy: {result['factual_accuracy']}")
        print("\nTop Matches:")
        for match in result['matches']:
            print(f"- {match['headline']} ({match['source']}, {match['similarity']:.2f})")
    except Exception as e:
        logger.critical(f"Error checking similarity: {str(e)}", exc_info=True)
        sys.exit(1)