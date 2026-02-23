# vocab/admin.py
from django.contrib import admin

from words.models import Word
from .models import TelegramUser, Card, Repetition

# Регистрируем модели
admin.site.register(TelegramUser)
admin.site.register(Card)
admin.site.register(Repetition)
admin.site.register(Word)


