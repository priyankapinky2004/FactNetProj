"""
Models for the Articles app
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from pymongo import MongoClient
import bson
from datetime import datetime


# Since we're using MongoDB for articles, we'll create proxy models that
# interact with the MongoDB collection. These don't actually create tables
# in the database but provide a Pythonic interface to work with MongoDB.

class ArticleManager:
    """Manager to interact with the MongoDB articles collection."""
    
    def __init__(self):
        """Initialize connection to MongoDB."""
        # Connection will be established when needed
        self.client = None
        self.db = None
        self.collection = None
    
    def connect(self):
        """Establish connection to MongoDB."""
        if not self.client:
            mongodb_uri = settings.DATABASES['default']['CLIENT']['host']
            mongodb_name = settings.DATABASES['default']['NAME']
            
            self.client = MongoClient(mongodb_uri)
            self.db = self.client[mongodb_name]
            self.collection = self.db['articles']
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.collection = None
    
    def get_articles(self, filters=None, page=1, per_page=10, sort_by=None):
        """
        Get articles from MongoDB with pagination.
        
        Args:
            filters: MongoDB query filter
            page: Page number (1-based)
            per_page: Number of items per page
            sort_by: Field to sort by, prefixed with - for descending
            
        Returns:
            Dictionary with articles and pagination info
        """
        self.connect()
        
        # Default filter if none provided
        if filters is None:
            filters = {}
        
        # Default sort
        if sort_by is None:
            sort_field = 'published_date'
            sort_direction = -1  # Descending
        else:
            if sort_by.startswith('-'):
                sort_field = sort_by[1:]
                sort_direction = -1
            else:
                sort_field = sort_by
                sort_direction = 1
        
        # Count total articles for pagination
        total_articles = self.collection.count_documents(filters)
        total_pages = (total_articles + per_page - 1) // per_page
        
        # Adjust page if out of range
        if page < 1:
            page = 1
        elif page > total_pages and total_pages > 0:
            page = total_pages
        
        # Get articles for the current page
        skip = (page - 1) * per_page
        articles = list(
            self.collection.find(filters)
            .sort(sort_field, sort_direction)
            .skip(skip)
            .limit(per_page)
        )
        
        # Convert MongoDB ObjectId to string
        for article in articles:
            article['id'] = str(article.pop('_id'))
        
        return {
            'articles': articles,
            'page': page,
            'per_page': per_page,
            'total_articles': total_articles,
            'total_pages': total_pages
        }
    
    def get_article(self, article_id):
        """
        Get a single article by ID.
        
        Args:
            article_id: MongoDB ObjectId or string
            
        Returns:
            Article dictionary or None if not found
        """
        self.connect()
        
        try:
            if isinstance(article_id, str):
                article_id = bson.ObjectId(article_id)
            
            article = self.collection.find_one({'_id': article_id})
            
            if article:
                article['id'] = str(article.pop('_id'))
            
            return article
        except bson.errors.InvalidId:
            return None
    
    def create_article(self, article_data):
        """
        Create a new article.
        
        Args:
            article_data: Dictionary with article data
            
        Returns:
            Created article with ID
        """
        self.connect()
        
        # Add timestamps
        now = datetime.utcnow()
        article_data['created_at'] = now
        article_data['updated_at'] = now
        
        # Initialize vote counters if not present
        if 'upvotes' not in article_data:
            article_data['upvotes'] = 0
        if 'downvotes' not in article_data:
            article_data['downvotes'] = 0
        
        # Insert into MongoDB
        result = self.collection.insert_one(article_data)
        
        # Get the created article
        article = self.get_article(result.inserted_id)
        
        return article
    
    def update_article(self, article_id, article_data):
        """
        Update an existing article.
        
        Args:
            article_id: MongoDB ObjectId or string
            article_data: Dictionary with article data
            
        Returns:
            Updated article or None if not found
        """
        self.connect()
        
        try:
            if isinstance(article_id, str):
                article_id = bson.ObjectId(article_id)
            
            # Add updated timestamp
            article_data['updated_at'] = datetime.utcnow()
            
            # Update in MongoDB
            self.collection.update_one(
                {'_id': article_id},
                {'$set': article_data}
            )
            
            # Get the updated article
            article = self.get_article(article_id)
            
            return article
        except bson.errors.InvalidId:
            return None
    
    def delete_article(self, article_id):
        """
        Delete an article.
        
        Args:
            article_id: MongoDB ObjectId or string
            
        Returns:
            True if deleted, False if not found
        """
        self.connect()
        
        try:
            if isinstance(article_id, str):
                article_id = bson.ObjectId(article_id)
            
            result = self.collection.delete_one({'_id': article_id})
            
            return result.deleted_count > 0
        except bson.errors.InvalidId:
            return False
    
    def check_similarity(self, article_text):
        """
        Check similarity between submitted text and trusted articles.
        
        Args:
            article_text: Text to check
            
        Returns:
            Similarity results
        """
        # Import here to avoid circular imports
        import sys
        import os
        
        # Add scripts directory to path
        scripts_dir = os.path.join(settings.BASE_DIR.parent, 'scripts')
        if scripts_dir not in sys.path:
            sys.path.append(scripts_dir)
        
        try:
            from similarity_checker import check_article_similarity
            
            # Get MongoDB connection parameters from settings
            mongodb_uri = settings.DATABASES['default']['CLIENT']['host']
            
            # Check similarity
            result = check_article_similarity(article_text, mongodb_uri)
            
            return result
        except ImportError:
            return {
                'overall_similarity': 0.0,
                'similarity_percentage': '0.0%',
                'factual_accuracy': 'Unknown',
                'error': 'Similarity checker module not found'
            }


# Singleton instance for article operations
articles = ArticleManager()


# For feedback submissions from users that relate to article fact-checking
class FactCheckFeedback(models.Model):
    """Model for user feedback on fact-checking results."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fact_check_feedback')
    article_id = models.CharField(max_length=50)  # MongoDB ID of the article
    
    # Feedback type
    FEEDBACK_CHOICES = (
        ('accurate', _('Accurate')),
        ('inaccurate', _('Inaccurate')),
        ('unsure', _('Unsure')),
    )
    feedback_type = models.CharField(max_length=10, choices=FEEDBACK_CHOICES)
    
    # Additional comments
    comment = models.TextField(blank=True, null=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Fact Check Feedback')
        verbose_name_plural = _('Fact Check Feedback')
        unique_together = ('user', 'article_id')