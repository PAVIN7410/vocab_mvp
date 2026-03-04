# vocab/admin.py
from django.contrib import admin
from words.models import Word
from .models import TelegramUser, Card, Repetition, UserSettings

# Регистрируем модели
@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'telegram_id', 'username', 'created_at']
    search_fields = ['telegram_id', 'username']

@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ['id', 'text', 'translation', 'user']
    list_filter = ['user']

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ['id', 'word', 'translation', 'owner', 'difficulty']
    list_filter = ['owner', 'difficulty']

@admin.register(Repetition)
class RepetitionAdmin(admin.ModelAdmin):
    list_display = ['id', 'card', 'next_review', 'repetitions', 'easiness']
    list_filter = ['next_review']

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'first_interval', 'voice_gender']