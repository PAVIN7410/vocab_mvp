#vocab/models.py:
import random

from django.contrib.auth.models import User
from django.db import models
from django.db.models import signals
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.shortcuts import render
from django.utils import timezone

from words.models import Word


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
    DIFFICULTY_CHOICES = (
        ('beginner', 'Начальный'),
        ('intermediate', 'Средний'),
        ('advanced', 'Продвинутый'),
    )

    owner = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name="cards")
    word = models.CharField(max_length=100)
    translation = models.CharField(max_length=200)
    example = models.TextField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='beginner')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.word} → {self.translation}"


class Repetition(models.Model):
    card = models.OneToOneField(Card, on_delete=models.CASCADE, related_name="repetition")
    next_review = models.DateTimeField()
    interval = models.IntegerField(default=0)  # days
    easiness = models.FloatField(default=2.5)  # EF из SM-2
    repetitions = models.IntegerField(default=0)  # успешные повторения
    review_count = models.IntegerField(default=0)  # всего повторений
    last_result = models.BooleanField(default=True)
    updated = models.DateTimeField(auto_now=True)



    def schedule_review(self, quality: int):
        """
        SM-2 алгоритм
        quality: 0-5 (0=полный провал, 5=отлично)
        """
        if quality < 3:
            # Неудача
            self.interval = 1
            self.repetitions = 0
        else:
            # Успех
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = int(self.interval * self.easiness)

            self.repetitions += 1

        # Обновляем легкость
        self.easiness = max(1.3, self.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        # Следующее повторение
        self.next_review = timezone.now() + timezone.timedelta(days=self.interval)
        self.review_count += 1
        self.last_result = quality >= 3

        self.save()

def __str__(self):
    return f"{self.card.word}: след. повторение {self.next_review}"




@receiver(post_save, sender=Card)
def create_repetition(sender, instance, created, **kwargs):
    if created:
        Repetition.objects.get_or_create(
            card=instance,
            defaults={
                'next_review': timezone.now(),
                'interval': 0,
                'easiness': 2.5,
                'repetitions': 0,
                'review_count': 0,
                'last_result': True
            }
        )



def test_view(request):
    # Получаем все слова
    words = Word.objects.all()
    if not words:
        return render(request, 'test_page.html', {'error': 'Нет доступных слов для тестирования.'})

    # Берём случайное
    word = random.choice(list(words))

    if request.method == 'POST':
        user_translation = request.POST.get('translation', '').strip().lower()
        correct_translation = word.translation.strip().lower()

        is_correct = user_translation == correct_translation
        return render(request, 'test_page.html', {
            'word': word,
            'user_translation': user_translation,
            'is_correct': is_correct
        })

    return render(request, 'test_page.html', {'word': word})

