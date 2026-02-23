#words/models.py:

from django.db import models
from django.utils import timezone




def word_image_upload_path(instance, filename):
    # Безопасное получение ID пользователя (если объект еще не сохранен)
    user_id = instance.user.id if instance.user and instance.user.id else "unknown"
    return f"word_images/user_{user_id}/{filename}"

class Word(models.Model):
    # Используем строку 'vocab.TelegramUser' для предотвращения кругового импорта
    user = models.ForeignKey(
        'vocab.TelegramUser',
        on_delete=models.CASCADE,
        related_name='words'
    )
    text = models.CharField(max_length=255)
    translation = models.CharField(max_length=255)

    source_lang = models.CharField(
        max_length=10,
        default='en',
        help_text='Language of the original word (en/ru)'
    )

    # Рекомендуется использовать callable (без скобок), чтобы дата бралась в момент создания
    next_review = models.DateTimeField(default=timezone.now)

    interval = models.IntegerField(default=1)
    repetitions = models.IntegerField(default=0)
    ease_factor = models.FloatField(default=2.5)

    image = models.ImageField(
        upload_to=word_image_upload_path,
        null=True,
        blank=True
    )

    def __str__(self):
        # Используем username пользователя, так как объект user может не иметь __str__
        return f"{self.text} ({self.user.username if self.user else 'No User'})"





