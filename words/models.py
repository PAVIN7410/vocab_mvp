#words/models.py:

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from bot.image_generator import fetch_image_for_word


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
    image = models.ImageField(upload_to='word_images/', blank=True, null=True)

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



