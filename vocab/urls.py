# vocab/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from . import views

#from vocab.views import progress_view  # ← Импортируем view
urlpatterns = [
    path('test/', views.test_view, name='test'),
    path('register/', views.register_user, name='register'),
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='words/')),  # Главная страница
    path('progress/', views.progress_view, name='progress'),
    path('review/', views.review_view, name='review'),  # ← Добавь эту строку
    path('words/', include('words.urls')),  # Маршруты из words
    path('settings/', views.settings_view, name='settings'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

