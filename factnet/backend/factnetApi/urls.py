from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

# Add this simple test view
def test_view(request):
    return HttpResponse("FactNet API is working!")

urlpatterns = [
    # Add this at the top
    path('test/', test_view, name='test_view'),
    
    # Keep your existing URLs
    path('admin/', admin.site.urls),
    # Instead of this:
    path('api/articles/', include('articles.urls')),

# Try this:
    #path('api/articles/', include('articles.urls')),
# or this:
    #path('api/articles/', include('factnet.backend.articles.urls')),
    # ...rest of your URLs
]