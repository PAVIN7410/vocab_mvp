# vocab/admin.py
from django.contrib import admin
from .models import TelegramUser, Card, Repetition, Word

# Регистрируем модели
admin.site.register(TelegramUser)
admin.site.register(Card)
admin.site.register(Repetition)
admin.site.register(Word)


