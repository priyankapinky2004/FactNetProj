"""
News Categorization Module for FactNet

This module provides functionality to categorize news articles into predefined 
categories using keyword matching and basic NLP techniques.

Usage:
    python news_categorizer.py [--mongodb MONGODB_URI]
"""

import os
import sys
import logging
import argparse
from typing import Dict, List, Any, Tuple

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_categorizer.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Download required NLTK resources
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')


class NewsCategorizer:
    """A class for categorizing news articles based on content analysis."""
    
    # Define categories with their associated keywords
    CATEGORIES = {
        "politics": [
            "government", "election", "president", "minister", "parliament", 
            "democracy", "vote", "policy", "campaign", "politician", "political",
            "democrat", "republican", "congress", "senate"
        ],
        "business": [
            "economy", "market", "stock", "investment", "company", "corporate", 
            "finance", "trade", "industry", "economic", "bank", "inflation",
            "recession", "profit", "revenue"
        ],
        "technology": [
            "software", "hardware", "app", "computer", "internet", "cyber", 
            "digital", "ai", "artificial intelligence", "robot", "innovation",
            "tech", "smartphone", "gadget", "data"
        ],
        "health": [
            "disease", "medicine", "doctor", "hospital", "patient", "medical", 
            "treatment", "healthcare", "virus", "pandemic", "vaccine", "drug",
            "cancer", "surgery", "diet"
        ],
        "science": [
            "research", "discovery", "experiment", "scientist", "study", 
            "physics", "chemistry", "biology", "space", "planet", "astronomy",
            "laboratory", "theory", "molecular", "scientific"
        ],
        "sports": [
            "match", "game", "player", "team", "tournament", "championship", 
            "coach", "athlete", "win", "score", "olympic", "ball", "league",
            "soccer", "football", "basketball"
        ],
        "entertainment": [
            "movie", "film", "music", "celebrity", "actor", "actress", "star", 
            "television", "tv", "show", "concert", "festival", "theater",
            "performance", "hollywood"
        ],
        "world": [
            "international", "foreign", "global", "country", "nation", "world", 
            "diplomatic", "embassy", "crisis", "conflict", "war", "peace",
            "treaty", "border", "immigration"
        ],
        "environment": [
            "climate", "environment", "green", "sustainable", "renewable", 
            "pollution", "carbon", "emission", "conservation", "wildlife",
            "ecosystem", "forest", "ocean", "biodiversity"
        ]
    }
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/"):
        """
        Initialize the categorizer with MongoDB connection.
        
        Args:
            mongo_uri: MongoDB connection string
        """
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client["factnet"]
        self.news_collection = self.db["articles"]
        
        # Load stopwords
        self.stop_words = set(stopwords.words('english'))
    
    def preprocess_text(self, text: str) -> List[str]:
        """
        Preprocess text by tokenizing, lowercasing, and removing stopwords.
        
        Args:
            text: Input text
            
        Returns:
            List of processed tokens
        """
        if not text:
            return []
            
        # Tokenize and lowercase
        tokens = word_tokenize(text.lower())
        
        # Remove stopwords and short words
        processed_tokens = [
            word for word in tokens 
            if word.isalpha() and word not in self.stop_words and len(word) > 2
        ]
        
        return processed_tokens
    
    def categorize_article(self, headline: str, content: str) -> Tuple[str, float, Dict[str, float]]:
        """
        Categorize an article based on its headline and content.
        
        Args:
            headline: The article headline
            content: The article content
            
        Returns:
            Tuple of (category, confidence, all_scores)
        """
        # Combine headline and content, giving headline more weight
        combined_text = f"{headline} {headline} {content}"
        
        # Preprocess the text
        tokens = self.preprocess_text(combined_text)
        
        if not tokens:
            return "uncategorized", 0.0, {}
        
        # Count keyword matches for each category
        category_scores = {category: 0 for category in self.CATEGORIES}
        
        for token in tokens:
            for category, keywords in self.CATEGORIES.items():
                if token in keywords:
                    category_scores[category] += 1
        
        # Normalize scores by token count
        total_tokens = len(tokens)
        for category in category_scores:
            category_scores[category] = category_scores[category] / total_tokens
        
        # Get the category with the highest score
        top_category = max(category_scores.items(), key=lambda x: x[1])
        
        # If the highest score is too low, mark as uncategorized
        if top_category[1] < 0.01:
            return "uncategorized", 0.0, category_scores
        
        return top_category[0], top_category[1], category_scores
    
    def process_uncategorized_articles(self) -> int:
        """
        Process all uncategorized articles in the database.
        
        Returns:
            Number of articles categorized
        """
        # Find uncategorized articles
        uncategorized = self.news_collection.find(
            {"category": None}
        )
        
        count = 0
        for article in uncategorized:
            headline = article.get("headline", "")
            content = article.get("content", "")
            
            # Skip articles with no content
            if not headline and not content:
                continue
            
            # Categorize the article
            category, confidence, scores = self.categorize_article(headline, content)
            
            # Update the article in the database
            self.news_collection.update_one(
                {"_id": article["_id"]},
                {"$set": {
                    "category": category,
                    "category_confidence": confidence,
                    "category_scores": scores
                }}
            )
            
            count += 1
            if count % 100 == 0:
                logger.info(f"Categorized {count} articles so far")
        
        logger.info(f"Categorized {count} articles in total")
        return count
    
    def close(self):
        """Close the MongoDB connection."""
        self.mongo_client.close()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Categorize news articles.')
    parser.add_argument('--mongodb', dest='mongo_uri', default="mongodb://localhost:27017/",
                        help='MongoDB connection URI')
    
    args = parser.parse_args()
    
    try:
        # Initialize and run the categorizer
        categorizer = NewsCategorizer(args.mongo_uri)
        categorizer.process_uncategorized_articles()
        categorizer.close()
    except Exception as e:
        logger.critical(f"Critical error in news categorizer: {str(e)}", exc_info=True)
        sys.exit(1)