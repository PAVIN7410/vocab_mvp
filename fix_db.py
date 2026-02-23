import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vocab.settings')
django.setup()

from vocab.models import Card, TelegramUser, Repetition
from django.contrib.auth.models import User
from django.utils import timezone


def fix():
    try:
        admin = User.objects.get(username='PAVIN')
        # Отвязываем админа от старых записей
        TelegramUser.objects.filter(user=admin).update(user=None)

        # Находим или создаем ваш реальный TG профиль
        tg_user, _ = TelegramUser.objects.get_or_create(telegram_id=1853366253)
        tg_user.user = admin
        tg_user.save()

        # Присваиваем ВСЕ карточки в базе вам
        total_cards = Card.objects.all().update(owner=tg_user)

        # Создаем записи о повторении для каждой карточки, если их нет
        created_reps = 0
        for card in Card.objects.all():
            _, created = Repetition.objects.get_or_create(
                card=card,
                defaults={'next_review': timezone.now()}
            )
            if created:
                created_reps += 1

        # Обнуляем время повторения для всех
        Repetition.objects.all().update(next_review=timezone.now())

        print(f"--- УСПЕХ ---")
        print(f"Пользователь PAVIN связан с ID 1853366253")
        print(f"Всего карточек перепривязано: {total_cards}")
        print(f"Создано новых записей повторения: {created_reps}")
        print(f"Все карточки готовы к повторению!")

    except Exception as e:
        print(f"ОШИБКА: {e}")


if __name__ == "__main__":
    fix()
