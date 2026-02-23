#  vocab/models.py

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class SomeModel(models.Model):
    word = models.ForeignKey('words.Word', on_delete=models.CASCADE)


class TelegramUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username or f"ID {self.telegram_id}"

    class Meta:
        app_label = 'vocab'


class UserSettings(models.Model):
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='settings')
    first_interval = models.IntegerField(default=1)
    second_interval = models.IntegerField(default=6)
    interval_multiplier = models.FloatField(default=1.0)
    max_interval = models.IntegerField(default=365)
    min_easiness = models.FloatField(default=1.3)
    voice_gender = models.CharField(
        max_length=10,
        choices=(('female', 'Женский'), ('male', 'Мужской')),
        default='female'
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Настройки {self.user}"




class BotLog(models.Model):
    telegram_id = models.BigIntegerField()
    command = models.CharField(max_length=64)
    request = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.command} от {self.telegram_id} ({self.timestamp})"


def card_image_upload_path(instance, filename):
    return f"card_images/user_{instance.owner.id}/{filename}"


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
    image = models.ImageField(upload_to=card_image_upload_path, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.word} → {self.translation}"


class Repetition(models.Model):
    card = models.OneToOneField(Card, on_delete=models.CASCADE, related_name="repetition")
    next_review = models.DateTimeField()
    interval = models.IntegerField(default=0)
    easiness = models.FloatField(default=2.5)
    repetitions = models.IntegerField(default=0)
    review_count = models.IntegerField(default=0)
    last_result = models.BooleanField(default=True)
    updated = models.DateTimeField(auto_now=True)

    def schedule_review(self, quality: int):
        try:
            settings = self.card.owner.settings
        except ObjectDoesNotExist:
            settings = UserSettings.objects.create(user=self.card.owner)

        if quality < 3:
            self.interval = settings.first_interval
            self.repetitions = 0
        else:
            if self.repetitions == 0:
                self.interval = settings.first_interval
            elif self.repetitions == 1:
                self.interval = settings.second_interval
            else:
                self.interval = int(self.interval * self.easiness * settings.interval_multiplier)
            self.interval = min(self.interval, settings.max_interval)
            self.repetitions += 1

        self.easiness = max(
            settings.min_easiness,
            self.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        )
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
        if not instance.image:
            try:
                from bot.image_generator import generate_image_for_word, ImageGenerationError
                from django.core.files import File
                import os
                img_path = generate_image_for_word(instance.word)
                with open(img_path, "rb") as f:
                    django_file = File(f, name=f"{instance.word}.png")
                    instance.image.save(django_file.name, django_file, save=True)
                if os.path.exists(img_path):
                    os.remove(img_path)
            except (ImageGenerationError, Exception) as e:
                print(f"Error generating image for card: {e}")


@receiver(post_save, sender='words.Word')
def create_cards_for_all_users(sender, instance, created, **kwargs):
    """
    При создании нового слова в админке, оно автоматически
    становится карточкой для ВСЕХ зарегистрированных пользователей.
    """
    if created:
        try:
            # 1. Получаем всех живых пользователей (кроме тестового, если он мешает)
            all_users = TelegramUser.objects.exclude(telegram_id=12345)

            if not all_users.exists():
                print("DEBUG: Новых пользователей пока нет. Карточки не созданы.")
                return

            # 2. Создаем карточки для каждого пользователя
            created_count = 0
            for tg_user in all_users:
                # Используем get_or_create, чтобы не дублировать, если слово уже есть
                _, card_created = Card.objects.get_or_create(
                    owner=tg_user,
                    word=instance.text,
                    defaults={
                        'translation': instance.translation,
                        'difficulty': 'beginner'
                    }
                )
                if card_created:
                    created_count += 1

            print(f"✅ Слово '{instance.text}' успешно добавлено {created_count} пользователям.")

        except Exception as e:
            print(f"❌ ОШИБКА В СИГНАЛЕ: {e}")
