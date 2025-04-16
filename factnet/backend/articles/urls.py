from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ArticleViewSet, FactCheckFeedbackViewSet

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'', ArticleViewSet, basename='articles')
router.register(r'feedback', FactCheckFeedbackViewSet, basename='feedback')

# This line is crucial - make sure it's exactly like this
urlpatterns = [
    path('', include(router.urls)),
]