"""
User models for FactNet
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom user model for FactNet.
    
    Extends the default Django user model with additional fields.
    """
    
    # Profile picture
    profile_picture = models.URLField(blank=True, null=True)
    
    # User role (regular user, admin, moderator)
    ROLE_CHOICES = (
        ('user', _('Regular User')),
        ('moderator', _('Moderator')),
        ('admin', _('Admin')),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    
    # Is this a verified user (through email verification or OAuth)
    is_verified = models.BooleanField(default=False)
    
    # Biography/description
    bio = models.TextField(blank=True, null=True)
    
    # User stats
    articles_submitted = models.IntegerField(default=0)
    fact_checks_requested = models.IntegerField(default=0)
    
    # Date fields
    date_modified = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.username
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')


class SavedArticle(models.Model):
    """
    Articles saved by users.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_articles')
    article_id = models.CharField(max_length=50)  # MongoDB ID of the article
    saved_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'article_id')
        verbose_name = _('Saved Article')
        verbose_name_plural = _('Saved Articles')


class UserActivity(models.Model):
    """
    Tracks user activities like upvotes, downvotes, etc.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    
    # Activity type
    ACTIVITY_CHOICES = (
        ('upvote', _('Upvote')),
        ('downvote', _('Downvote')),
        ('fact_check', _('Fact Check Request')),
        ('submit', _('Article Submission')),
    )
    activity_type = models.CharField(max_length=10, choices=ACTIVITY_CHOICES)
    
    # Related article
    article_id = models.CharField(max_length=50)  # MongoDB ID of the article
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('User Activity')
        verbose_name_plural = _('User Activities')