"""
Serializers for the Users app
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from ..users.models import SavedArticle, UserActivity


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user objects."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'profile_picture', 'role', 'is_verified', 'bio',
                 'articles_submitted', 'fact_checks_requested', 'date_joined']
        read_only_fields = ['id', 'role', 'is_verified', 'articles_submitted', 
                           'fact_checks_requested', 'date_joined']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'profile_picture', 'bio', 'date_joined']
        read_only_fields = ['id', 'username', 'email', 'date_joined']


class SavedArticleSerializer(serializers.ModelSerializer):
    """Serializer for saved articles."""
    
    class Meta:
        model = SavedArticle
        fields = ['id', 'user', 'article_id', 'saved_date']
        read_only_fields = ['id', 'user', 'saved_date']


class UserActivitySerializer(serializers.ModelSerializer):
    """Serializer for user activities."""
    
    class Meta:
        model = UserActivity
        fields = ['id', 'user', 'activity_type', 'article_id', 'timestamp']
        read_only_fields = ['id', 'user', 'timestamp']


class GoogleAuthSerializer(serializers.Serializer):
    """
    Serializer for Google authentication.
    
    Takes the access token from the Google OAuth2 flow and returns user info.
    """
    code = serializers.CharField(required=True)
    redirect_uri = serializers.CharField(required=True)