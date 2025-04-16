from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, UserProfileView, SavedArticleViewSet, 
    UserActivityViewSet, GoogleLogin
)

# Create a router for ViewSets
router = DefaultRouter()
router.register('users', UserViewSet)
router.register('saved-articles', SavedArticleViewSet, basename='saved-articles')
router.register('activities', UserActivityViewSet, basename='activities')

urlpatterns = [
    path('', include(router.urls)),
    path('profile/', UserProfileView.as_view(), name='user-profile'),
    path('google/', GoogleLogin.as_view(), name='google-login'),
]