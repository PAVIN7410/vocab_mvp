#vocab/models.py:

from django.db import models
from django.contrib.auth.models import User
from django.db import models

class TelegramUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username or f"ID {self.telegram_id}"

    class Meta:
        app_label = 'vocab'


class BotLog(models.Model):
    telegram_id = models.BigIntegerField()
    command = models.CharField(max_length=64)
    request = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.command} от {self.telegram_id} ({self.timestamp})"



class Card(models.Model):
    DIFFICULTY = (
        ('beginner', 'Начальный'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый'),
    )
    DIFFICULTY = (
        ('beginner', 'Начальный'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый'),
    )

    owner = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="cards")
    word = models.CharField(max_length=64)
    translation = models.CharField(max_length=128)
    example = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    difficulty = models.CharField(max_length=16, choices=DIFFICULTY, default='beginner')
    created = models.DateTimeField(auto_now_add=True)

class Repetition(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    next_review = models.DateTimeField()
    interval = models.IntegerField(default=1)  # days
    easiness = models.FloatField(default=2.5)
    repetitions = models.IntegerField(default=0)
    review_count = models.IntegerField(default=0)
    last_result = models.BooleanField(default=True)
    updated = models.DateTimeField(auto_now=True)



