from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic.base import TemplateView
from .views import user_logout, user_login

urlpatterns = [
    path('logout/', user_logout, name='logout'),
    path('login/', user_login, name='login'),
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain"), ),
    path('', include('django.contrib.auth.urls')),
    path('change-password', auth_views.PasswordChangeView.as_view(template_name='registration/change-password.html'), name='change-password'),
    path('', include('league.urls')),
]
