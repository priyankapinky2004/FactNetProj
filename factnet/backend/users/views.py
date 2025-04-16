"""
Views for the Users app
"""

from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import SavedArticle, UserActivity
from ..users.serializers import (
    UserSerializer, UserProfileSerializer, SavedArticleSerializer, 
    UserActivitySerializer, GoogleAuthSerializer
)
from social_django.utils import load_strategy
from social_core.backends.google import GoogleOAuth2
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing user instances."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]


class UserProfileView(generics.RetrieveUpdateAPIView):
    """View for retrieving and updating user profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class SavedArticleViewSet(viewsets.ModelViewSet):
    """ViewSet for saved articles."""
    serializer_class = SavedArticleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return SavedArticle.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserActivityViewSet(viewsets.ModelViewSet):
    """ViewSet for user activities."""
    serializer_class = UserActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserActivity.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        
        # If this is an upvote or downvote, update the article in MongoDB
        activity_type = serializer.validated_data.get('activity_type')
        article_id = serializer.validated_data.get('article_id')
        
        if activity_type in ['upvote', 'downvote'] and article_id:
            from pymongo import MongoClient
            from django.conf import settings
            import bson
            
            # Connect to MongoDB
            client = MongoClient(settings.DATABASES['default']['CLIENT']['host'])
            db = client[settings.DATABASES['default']['NAME']]
            collection = db['articles']
            
            # Convert string ID to ObjectId
            try:
                object_id = bson.ObjectId(article_id)
                
                # Update the article
                update_field = 'upvotes' if activity_type == 'upvote' else 'downvotes'
                collection.update_one(
                    {'_id': object_id},
                    {'$inc': {update_field: 1}}
                )
            except bson.errors.InvalidId:
                pass
            finally:
                client.close()


class GoogleLogin(generics.GenericAPIView):
    """View for Google OAuth2 login."""
    serializer_class = GoogleAuthSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Process the Google authentication."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data.get('code')
        redirect_uri = serializer.validated_data.get('redirect_uri')
        
        # Load the Google OAuth2 strategy
        strategy = load_strategy(request)
        backend = GoogleOAuth2(strategy)
        
        try:
            # Exchange the code for user data
            user_data = backend.do_auth(
                code,
                redirect_uri=redirect_uri
            )
            
            # Get or create the user
            user = backend.strategy.storage.user.get_user(user_data['id'])
            if not user:
                user = backend.strategy.storage.user.create_user(user_data['id'])
            
            # Update user fields
            user.email = user_data.get('email', '')
            user.first_name = user_data.get('first_name', '')
            user.last_name = user_data.get('last_name', '')
            user.profile_picture = user_data.get('picture', '')
            user.is_verified = user_data.get('email_verified', False)
            user.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )