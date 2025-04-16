"""
Views for the Articles app
"""

from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from django.utils.translation import gettext_lazy as _

from .models import articles, FactCheckFeedback
from ..articles.serializers import (
    ArticleSerializer, FactCheckRequestSerializer, FactCheckResultSerializer,
    FactCheckFeedbackSerializer, ArticleVoteSerializer
)


class ArticleViewSet(viewsets.ViewSet):
    """
    ViewSet for working with articles from MongoDB.
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def list(self, request):
        """
        List articles with filtering and pagination.
        """
        # Get query parameters
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 10))
        category = request.query_params.get('category')
        source = request.query_params.get('source')
        sort_by = request.query_params.get('sort_by', '-published_date')
        search = request.query_params.get('search')
        
        # Build filters
        filters = {}
        
        if category:
            filters['category'] = category
        
        if source:
            filters['source'] = source
        
        if search:
            # Text search in headline and content
            filters['$or'] = [
                {'headline': {'$regex': search, '$options': 'i'}},
                {'content': {'$regex': search, '$options': 'i'}}
            ]
        
        # Get articles from MongoDB
        result = articles.get_articles(
            filters=filters,
            page=page,
            per_page=per_page,
            sort_by=sort_by
        )
        
        # Serialize articles
        serializer = ArticleSerializer(result['articles'], many=True)
        
        # Return paginated result
        return Response({
            'results': serializer.data,
            'count': result['total_articles'],
            'next': f"?page={result['page'] + 1}" if result['page'] < result['total_pages'] else None,
            'previous': f"?page={result['page'] - 1}" if result['page'] > 1 else None,
        })
    
    def retrieve(self, request, pk=None):
        """
        Retrieve a single article.
        """
        article = articles.get_article(pk)
        
        if not article:
            raise NotFound(_("Article not found"))
        
        serializer = ArticleSerializer(article)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Create a new article.
        """
        serializer = ArticleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Add user info
        article_data = serializer.validated_data
        article_data['submitted_by'] = request.user.username
        
        # Create article
        article = articles.create_article(article_data)
        
        # Update user stats
        request.user.articles_submitted += 1
        request.user.save()
        
        return Response(ArticleSerializer(article).data, status=status.HTTP_201_CREATED)
    
    def update(self, request, pk=None):
        """
        Update an article.
        """
        article = articles.get_article(pk)
        
        if not article:
            raise NotFound(_("Article not found"))
        
        # Check permissions (only allow admin or the submitter)
        if not request.user.is_staff and article.get('submitted_by') != request.user.username:
            return Response(
                {"detail": _("You do not have permission to edit this article.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ArticleSerializer(data=request.data, instance=article)
        serializer.is_valid(raise_exception=True)
        
        # Update article
        updated_article = articles.update_article(pk, serializer.validated_data)
        
        return Response(ArticleSerializer(updated_article).data)
    
    def destroy(self, request, pk=None):
        """
        Delete an article.
        """
        article = articles.get_article(pk)
        
        if not article:
            raise NotFound(_("Article not found"))
        
        # Check permissions (only allow admin or the submitter)
        if not request.user.is_staff and article.get('submitted_by') != request.user.username:
            return Response(
                {"detail": _("You do not have permission to delete this article.")},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Delete article
        result = articles.delete_article(pk)
        
        if result:
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response(
                {"detail": _("Failed to delete article.")},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def fact_check(self, request):
        """
        Check factual accuracy of submitted text.
        """
        serializer = FactCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get the article text
        title = serializer.validated_data.get('title', '')
        content = serializer.validated_data.get('content', '')
        
        # Combine title and content
        article_text = f"{title}\n\n{content}"
        
        # Check similarity
        similarity_result = articles.check_similarity(article_text)
        
        # Update user stats
        request.user.fact_checks_requested += 1
        request.user.save()
        
        # Return results
        result_serializer = FactCheckResultSerializer(similarity_result)
        return Response(result_serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def vote(self, request, pk=None):
        """
        Vote on an article (upvote or downvote).
        """
        article = articles.get_article(pk)
        
        if not article:
            raise NotFound(_("Article not found"))
        
        # Validate vote
        serializer = ArticleVoteSerializer(data={
            'article_id': pk,
            'vote_type': request.data.get('vote_type')
        })
        serializer.is_valid(raise_exception=True)
        
        # Record user activity
        from users.models import UserActivity
        UserActivity.objects.create(
            user=request.user,
            activity_type=serializer.validated_data.get('vote_type'),
            article_id=pk
        )
        
        # Update article in MongoDB
        vote_type = serializer.validated_data.get('vote_type')
        articles.connect()
        try:
            field = 'upvotes' if vote_type == 'upvote' else 'downvotes'
            articles.collection.update_one(
                {'_id': articles.collection.database.command('converter', {'string': pk})}
                if isinstance(pk, str) else {'_id': pk},
                {'$inc': {field: 1}}
            )
            
            # Get updated article
            updated_article = articles.get_article(pk)
            
            return Response(ArticleSerializer(updated_article).data)
        except Exception as e:
            raise ValidationError(str(e))
        finally:
            articles.close()


class FactCheckFeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for fact check feedback.
    """
    serializer_class = FactCheckFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return FactCheckFeedback.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)