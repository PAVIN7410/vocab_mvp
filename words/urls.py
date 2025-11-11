# words/urls.py
from django.urls import path, reverse_lazy
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.WordListView.as_view(), name='word-list'),
    path('new/', RedirectView.as_view(url='/words/create/'), name='word-new'),  # /new/ → /create/
    path('create/', views.WordCreateView.as_view(), name='word-create'),
    path('<int:pk>/', views.WordDetailView.as_view(), name='word-detail'),
    path('update/<int:pk>/', views.WordUpdateView.as_view(), name='word-update'),
    path('delete/<int:pk>/', views.WordDeleteView.as_view(), name='word-delete'),
    path('test/', views.test_view, name='test'),
    path('translate/', views.translate_word, name='translate_word'),
    path('register/', views.register_user, name='register_user'),
    path('audio/<int:pk>/<str:text_type>/', views.generate_audio, name='generate_audio'),
    # Новые пути для озвучки — под старый фронтенд
    path('<int:pk>/audio/', views.generate_audio, {'text_type': 'word'}, name='word-audio'),
    path('<int:pk>/audio-translation/', views.generate_audio, {'text_type': 'translation'},name='word-translation-audio'),
    path('speak/', views.speak_text, name='speak_text'),  # ← НОВЫЙ ПУТЬ

]
