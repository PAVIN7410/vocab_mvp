# vocab/models.py

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from bot.image_generator import fetch_image_for_word
from words.models import Word


class SomeModel(models.Model):
    """
    Пример связи с моделью Word из приложения words.
    """
    word = models.ForeignKey('words.Word', on_delete=models.CASCADE)


class TelegramUser(models.Model):
    """
    Пользователь Telegram, связанный (опционально) с Django User.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    telegram_id = models.CharField(max_length=50, unique=True)  # ← Строка!
    username = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username or f"ID {self.telegram_id}"

    class Meta:
        app_label = 'vocab'


class UserSettings(models.Model):
    """
    Настройки интервального повторения и голосовых параметров
    для конкретного TelegramUser.
    """
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
    """
    Лог запросов/ответов бота.
    """
    telegram_id = models.BigIntegerField()
    command = models.CharField(max_length=64)
    request = models.TextField()
    response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.command} от {self.telegram_id} ({self.timestamp})"


def card_image_upload_path(instance, filename):
    """
    Путь для сохранения изображений карточек пользователя.
    """
    return f"card_images/user_{instance.owner.id}/{filename}"


class Card(models.Model):
    """
    Карточка слова для конкретного TelegramUser.
    """
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
    """
    Параметры интервального повторения для карточки.
    """
    card = models.OneToOneField(Card, on_delete=models.CASCADE, related_name="repetition")
    next_review = models.DateTimeField()
    interval = models.IntegerField(default=0)
    easiness = models.FloatField(default=2.5)
    repetitions = models.IntegerField(default=0)
    review_count = models.IntegerField(default=0)
    last_result = models.BooleanField(default=True)
    updated = models.DateTimeField(auto_now=True)

    def schedule_review(self, quality: int):
        """
        Обновляет параметры интервального повторения по оценке quality (0–5).
        """
        try:
            settings_obj = self.card.owner.settings
        except ObjectDoesNotExist:
            settings_obj = UserSettings.objects.create(user=self.card.owner)

        if quality < 3:
            self.interval = settings_obj.first_interval
            self.repetitions = 0
        else:
            if self.repetitions == 0:
                self.interval = settings_obj.first_interval
            elif self.repetitions == 1:
                self.interval = settings_obj.second_interval
            else:
                self.interval = int(self.interval * self.easiness * settings_obj.interval_multiplier)
            self.interval = min(self.interval, settings_obj.max_interval)
            self.repetitions += 1

        self.easiness = max(
            settings_obj.min_easiness,
            self.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        )
        self.next_review = timezone.now() + timezone.timedelta(days=self.interval)
        self.review_count += 1
        self.last_result = quality >= 3
        self.save()

    def __str__(self):
        return f"{self.card.word}: след. повторение {self.next_review}"


# === СИГНАЛЫ ===

@receiver(post_save, sender=Card)
def create_repetition_and_card_image(sender, instance: Card, created: bool, **kwargs):
    """
    1) При создании новой карточки создаём запись Repetition.
    2) Если у карточки ещё нет изображения — генерируем его и сохраняем в Card.image.
    """
    if not created:
        return

    # 1. Repetition
    Repetition.objects.get_or_create(
        card=instance,
        defaults={
            'next_review': timezone.now(),
            'interval': 0,
            'easiness': 2.5,
            'repetitions': 0,
            'review_count': 0,
            'last_result': True,
        }
    )

    # 2. Картинка для карточки
    if instance.image:
        return

    django_file = fetch_image_for_word(instance.word, instance.translation)
    if django_file is None:
        return

    instance.image.save(django_file.name, django_file, save=True)


@receiver(post_save, sender=Word)
def create_cards_for_all_users(sender, instance: Word, created: bool, **kwargs):
    """
    При создании нового слова (words.Word) оно автоматически
    становится карточкой для ВСЕХ зарегистрированных TelegramUser.
    """
    if not created:
        return

    try:
        all_users = TelegramUser.objects.all()

        if not all_users.exists():
            print("DEBUG: Новых пользователей пока нет. Карточки не созданы.")
            return

        created_count = 0
        for tg_user in all_users:
            _, card_created = Card.objects.get_or_create(
                owner=tg_user,
                word=instance.text,
                defaults={
                    'translation': instance.translation,
                    'difficulty': 'beginner',
                }
            )
            if card_created:
                created_count += 1

        print(f"✅ Слово '{instance.text}' успешно добавлено {created_count} пользователям.")

    except Exception as e:
        print(f"❌ ОШИБКА В СИГНАЛЕ create_cards_for_all_users: {e}")
