"""
News Aggregator for FactNet

This script collects news articles from various sources using RSS feeds,
extracts relevant information, and stores them in MongoDB.

Usage:
    python news_aggregator.py [--mongodb MONGODB_URI]
"""

import os
import sys
import logging
import argparse
import json
import feedparser
import requests
from datetime import datetime
from pymongo import MongoClient
from typing import Dict, List, Any, Optional
import re
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("news_aggregator.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NewsAggregator:
    """Class for aggregating news from various sources and storing in MongoDB."""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017/"):
        """
        Initialize the news aggregator with MongoDB connection.
        
        Args:
            mongo_uri: MongoDB connection string
        """
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client["factnet"]
        self.news_collection = self.db["articles"]
        
        # Create indexes for efficient querying
        self.news_collection.create_index("url", unique=True)
        self.news_collection.create_index("published_date")
        self.news_collection.create_index("source")
        self.news_collection.create_index("category")
    
    def parse_date(self, date_string: str) -> datetime:
        """
        Parse a date string to datetime object with error handling.
        
        Args:
            date_string: Date string in various formats
            
        Returns:
            datetime object
        """
        try:
            # Try parsing with feedparser's date handler
            return datetime(*feedparser._parse_date(date_string)[:6])
        except (TypeError, ValueError):
            try:
                # Try ISO format
                return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Fallback to current time
                logger.warning(f"Could not parse date: {date_string}, using current time")
                return datetime.utcnow()
    
    def clean_html(self, html_content: str) -> str:
        """
        Remove HTML tags from content.
        
        Args:
            html_content: HTML content string
            
        Returns:
            Cleaned text
        """
        if not html_content:
            return ""
        clean_text = re.sub(r'<.*?>', '', html_content)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return clean_text
    
    def extract_domain(self, url: str) -> str:
        """
        Extract domain name from URL.
        
        Args:
            url: Full URL string
            
        Returns:
            Domain name
        """
        try:
            parsed_uri = urlparse(url)
            domain = parsed_uri.netloc
            # Remove 'www.' if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return url
    
    def fetch_bbc_news(self) -> List[Dict[str, Any]]:
        """
        Fetch news from BBC RSS feeds.
        
        Returns:
            List of parsed news articles
        """
        bbc_feeds = [
            "http://feeds.bbci.co.uk/news/world/rss.xml",
            "http://feeds.bbci.co.uk/news/uk/rss.xml",
            "http://feeds.bbci.co.uk/news/business/rss.xml",
            "http://feeds.bbci.co.uk/news/politics/rss.xml",
            "http://feeds.bbci.co.uk/news/technology/rss.xml",
            "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
            "http://feeds.bbci.co.uk/news/health/rss.xml",
        ]
        
        articles = []
        
        for feed_url in bbc_feeds:
            try:
                logger.info(f"Fetching BBC RSS feed: {feed_url}")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries:
                    article = {
                        "headline": entry.title,
                        "url": entry.link,
                        "source": "BBC",
                        "published_date": self.parse_date(entry.published),
                        "content": self.clean_html(entry.summary if hasattr(entry, 'summary') else ""),
                        "category": None,  # Will be determined by categorizer
                        "is_trusted": True,  # BBC is considered a trusted source
                        "upvotes": 0,
                        "downvotes": 0,
                        "fetched_date": datetime.utcnow()
                    }
                    articles.append(article)
            except Exception as e:
                logger.error(f"Error fetching BBC feed {feed_url}: {str(e)}")
        
        return articles
    
    def fetch_reuters_news(self) -> List[Dict[str, Any]]:
        """
        Fetch news from Reuters RSS feeds.
        
        Returns:
            List of parsed news articles
        """
        reuters_feeds = [
            "https://www.reutersagency.com/feed/?best-topics=all&post_type=best",
            "https://www.reutersagency.com/feed/?best-regions=north-america&post_type=best",
            "https://www.reutersagency.com/feed/?best-regions=asia&post_type=best",
            "https://www.reutersagency.com/feed/?best-regions=europe&post_type=best",
            "https://www.reutersagency.com/feed/?best-sectors=economy&post_type=best",
        ]
        
        articles = []
        
        for feed_url in reuters_feeds:
            try:
                logger.info(f"Fetching Reuters RSS feed: {feed_url}")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries:
                    article = {
                        "headline": entry.title,
                        "url": entry.link,
                        "source": "Reuters",
                        "published_date": self.parse_date(entry.published if hasattr(entry, 'published') else ""),
                        "content": self.clean_html(entry.summary if hasattr(entry, 'summary') else ""),
                        "category": None,  # Will be determined by categorizer
                        "is_trusted": True,  # Reuters is considered a trusted source
                        "upvotes": 0,
                        "downvotes": 0,
                        "fetched_date": datetime.utcnow()
                    }
                    articles.append(article)
            except Exception as e:
                logger.error(f"Error fetching Reuters feed {feed_url}: {str(e)}")
        
        return articles
    
    def fetch_all_news(self) -> List[Dict[str, Any]]:
        """
        Fetch news from all configured sources.
        
        Returns:
            List of all parsed news articles
        """
        all_articles = []
        
        # Fetch from each source
        all_articles.extend(self.fetch_bbc_news())
        all_articles.extend(self.fetch_reuters_news())
        
        logger.info(f"Fetched a total of {len(all_articles)} articles")
        return all_articles
    
    def store_news(self, articles: List[Dict[str, Any]]) -> int:
        """
        Store news articles in MongoDB, avoiding duplicates.
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            Number of new articles stored
        """
        new_articles_count = 0
        
        for article in articles:
            try:
                # Use URL as unique identifier to avoid duplicates
                result = self.news_collection.update_one(
                    {"url": article["url"]},
                    {"$setOnInsert": article},
                    upsert=True
                )
                
                if result.upserted_id:
                    new_articles_count += 1
            except Exception as e:
                logger.error(f"Error storing article {article['url']}: {str(e)}")
        
        logger.info(f"Stored {new_articles_count} new articles in the database")
        return new_articles_count
    
    def run(self) -> None:
        """Run the full aggregation process."""
        logger.info("Starting news aggregation process")
        articles = self.fetch_all_news()
        new_count = self.store_news(articles)
        logger.info(f"News aggregation completed. {new_count} new articles added.")
    
    def close(self) -> None:
        """Close MongoDB connection."""
        self.mongo_client.close()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fetch news articles from various sources.')
    parser.add_argument('--mongodb', dest='mongo_uri', default="mongodb://localhost:27017/",
                        help='MongoDB connection URI')
    
    args = parser.parse_args()
    
    try:
        # Initialize and run the aggregator
        aggregator = NewsAggregator(args.mongo_uri)
        aggregator.run()
        aggregator.close()
    except Exception as e:
        logger.critical(f"Critical error in news aggregator: {str(e)}", exc_info=True)
        sys.exit(1)