#words/models.py:

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from bot.image_generator import fetch_image_for_word
from vocab.models import TelegramUser


def word_image_upload_path(instance, filename):
    # Безопасное получение ID пользователя (если объект еще не сохранен)
    user_id = instance.user.id if instance.user and instance.user.id else "unknown"
    return f"word_images/user_{user_id}/{filename}"


class Meta:
    unique_together = ['user', 'text']  # Одно слово один раз на юзера


class Word(models.Model):
    user = models.ForeignKey(
        'vocab.TelegramUser',
        on_delete=models.CASCADE,
        related_name='words',
        null=True, blank=True  # ← Разрешаем null временно
    )
    text = models.CharField(max_length=255)
    translation = models.CharField(max_length=255)

    source_lang = models.CharField(max_length=10, default='en')
    next_review = models.DateTimeField(default=timezone.now)
    interval = models.IntegerField(default=1)
    repetitions = models.IntegerField(default=0)
    ease_factor = models.FloatField(default=2.5)

    class Meta:
        unique_together = ['user', 'text']  # ← Защита от дублей

    def __str__(self):
        return f"{self.text} ({self.user.username if self.user else 'No User'})"

    def save(self, *args, **kwargs):
        """Автосвязка к основному пользователю если нет"""
        if not self.user:
            try:
                main_user = TelegramUser.objects.first()
                if main_user:
                    self.user = main_user
            except:
                pass
        super().save(*args, **kwargs)



@receiver(post_save, sender=Word)
def add_image_to_word(sender, instance: Word, created: bool, **kwargs):
    if not created:
        return
    if instance.image:
        return

    prompt = f"{instance.text} ({instance.translation})"
    django_file = fetch_image_for_word(instance.text, instance.translation)
    if django_file is None:
        return

    save = instance.image.save(django_file.name, django_file, save=True)



