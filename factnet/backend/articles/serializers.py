"""
Serializers for the Articles app
"""

from rest_framework import serializers
from ..articles.models import FactCheckFeedback


class ArticleSerializer(serializers.Serializer):
    """Serializer for articles from MongoDB."""
    id = serializers.CharField(read_only=True)
    headline = serializers.CharField(max_length=255)
    content = serializers.CharField()
    url = serializers.URLField()
    source = serializers.CharField(max_length=100)
    published_date = serializers.DateTimeField(required=False)
    category = serializers.CharField(max_length=50, required=False, allow_null=True)
    is_trusted = serializers.BooleanField(default=False)
    upvotes = serializers.IntegerField(default=0, read_only=True)
    downvotes = serializers.IntegerField(default=0, read_only=True)
    fetched_date = serializers.DateTimeField(required=False)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    def validate_url(self, value):
        """Validate that URL is unique."""
        from ..articles.models import articles
        
        # Don't validate on update
        if self.instance:
            return value
        
        # Check if article with this URL already exists
        articles.connect()
        existing = articles.collection.find_one({'url': value})
        articles.close()
        
        if existing:
            raise serializers.ValidationError("Article with this URL already exists.")
        
        return value


class FactCheckRequestSerializer(serializers.Serializer):
    """Serializer for fact check requests."""
    title = serializers.CharField(max_length=255)
    content = serializers.CharField()
    url = serializers.URLField(required=False, allow_blank=True)
    source = serializers.CharField(max_length=100, required=False, allow_blank=True)


class FactCheckResultSerializer(serializers.Serializer):
    """Serializer for fact check results."""
    overall_similarity = serializers.FloatField()
    similarity_percentage = serializers.CharField()
    factual_accuracy = serializers.CharField()
    matches = serializers.ListField(child=serializers.DictField())


class FactCheckFeedbackSerializer(serializers.ModelSerializer):
    """Serializer for fact check feedback."""
    
    class Meta:
        model = FactCheckFeedback
        fields = ['id', 'user', 'article_id', 'feedback_type', 'comment', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
    
    def create(self, validated_data):
        """Create a new feedback or update existing."""
        user = self.context['request'].user
        article_id = validated_data.get('article_id')
        
        # Look for existing feedback
        instance, created = FactCheckFeedback.objects.update_or_create(
            user=user,
            article_id=article_id,
            defaults={
                'feedback_type': validated_data.get('feedback_type'),
                'comment': validated_data.get('comment')
            }
        )
        
        return instance


class ArticleVoteSerializer(serializers.Serializer):
    """Serializer for article votes."""
    article_id = serializers.CharField()
    vote_type = serializers.ChoiceField(choices=['upvote', 'downvote'])
    
    def create(self, validated_data):
        """Process the vote."""
        from ..articles.models import articles
        
        article_id = validated_data.get('article_id')
        vote_type = validated_data.get('vote_type')
        
        # Update the article in MongoDB
        articles.connect()
        try:
            article_obj_id = articles.collection.find_one({'_id': article_id})
            if not article_obj_id:
                raise serializers.ValidationError("Article not found")
            
            # Increment the appropriate counter
            field = 'upvotes' if vote_type == 'upvote' else 'downvotes'
            articles.collection.update_one(
                {'_id': article_obj_id},
                {'$inc': {field: 1}}
            )
            
            # Get updated article
            updated_article = articles.get_article(article_id)
            articles.close()
            
            return updated_article
        except Exception as e:
            articles.close()
            raise serializers.ValidationError(str(e))