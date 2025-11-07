# words/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.WordListView.as_view(), name='word-list'),
    path('<int:pk>/', views.WordDetailView.as_view(), name='word-detail'),
    path('new/', views.WordCreateView.as_view(), name='word-create'),
    path('<int:pk>/edit/', views.WordUpdateView.as_view(), name='word-update'),
    path('<int:pk>/delete/', views.WordDeleteView.as_view(), name='word-delete'),
    path('<int:pk>/tts/', views.tts_view, name='word-tts'),
    path('translate/', views.translate_word, name='translate-word'),
    path('<int:pk>/audio/', views.word_audio_view, name='word-audio'),
    path('<int:pk>/audio-translation/', views.word_translation_audio_view, name='word-translation-audio'),
]
