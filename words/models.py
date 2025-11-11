#words/models.py:

from django.db import models
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from django.utils import timezone

class Word(models.Model):
    user = models.ForeignKey(
        'vocab.TelegramUser',  # Полная ссылка на модель из другого приложения
        on_delete=models.CASCADE,
        related_name='words_words'  # Уникальное имя для этой связи
    )
    text = models.CharField(max_length=255)
    translation = models.CharField(max_length=255)
    source_lang = models.CharField(max_length=10, default='en', help_text='Language of the original word (en/ru)')
    next_review = models.DateTimeField(default=timezone.now)
    interval = models.IntegerField(default=1)
    repetitions = models.IntegerField(default=0)
    ease_factor = models.FloatField(default=2.5)

    def __str__(self):
        return self.text




