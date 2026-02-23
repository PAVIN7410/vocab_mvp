# vocab/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from words.models import Word
from .models import Card, TelegramUser  # ← Это нормально, если не в models.py


@receiver(post_save, sender=Word)
def create_card_for_word(sender, instance, created, **kwargs):
    """
    При создании слова — создаёт карточку для повторения
    """
    if created:
        # Получаем или создаём тестового пользователя
        telegram_user, _ = TelegramUser.objects.get_or_create(
            telegram_id=12345,
            defaults={'username': 'test_user'}
        )
        # Создаём карточку
        Card.objects.get_or_create(
            owner=telegram_user,
            word=instance.text,
            translation=instance.translation,
            difficulty='beginner'
        )

