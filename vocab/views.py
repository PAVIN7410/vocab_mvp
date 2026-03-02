# vocab/views.py

import logging

from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Repetition, UserSettings, TelegramUser, Card

logger = logging.getLogger(__name__)


# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ЮЗЕРА ИЗ СЕССИИ ===

def get_tg_user(request: HttpRequest):
    """
    Достаём TelegramUser по telegram_id из сессии.
    Этот telegram_id один раз устанавливается во время входа с бота.
    """
    tg_id = request.session.get('telegram_id')
    if not tg_id:
        return None
    try:
        return TelegramUser.objects.get(telegram_id=tg_id)
    except TelegramUser.DoesNotExist:
        return None


# === ВХОД ЧЕРЕЗ БОТА ===

def bot_login_view(request: HttpRequest) -> HttpResponse:
    telegram_id = request.GET.get('telegram_id')
    username = request.GET.get('username')

    if not telegram_id:
        return HttpResponse("telegram_id is required", status=400)

    tg_user, _ = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={'username': username}
    )

    # ВАЖНО: ключ должен совпадать с тем, что читает get_tg_user
    request.session['telegram_id'] = int(telegram_id)

    return HttpResponseRedirect(reverse('review'))

# === СТРАНИЦА ПОВТОРЕНИЯ ===

def review_view(request: HttpRequest) -> HttpResponse:
    """
    Страница повторения слов для текущего TelegramUser.
    НЕ использует стандартный Django login, только telegram_id в сессии.
    """
    tg_user = get_tg_user(request)
    if not tg_user:
        return render(
            request,
            'review.html',
            {
                'error': 'Пожалуйста, откройте сайт по ссылке из Telegram-бота.'
            }
        )

    due_repetitions = (
        Repetition.objects
        .filter(card__owner=tg_user, next_review__lte=timezone.now())
        .select_related('card')
        .order_by('next_review')
    )

    if not due_repetitions.exists():
        return render(request, 'review.html', {'message': 'Нет слов для повторения. Молодец!'})

    repetition = due_repetitions.first()

    if request.method == 'POST':
        quality = int(request.POST.get('quality', 3))
        repetition.schedule_review(quality)
        return HttpResponseRedirect(reverse('review'))

    return render(request, 'review.html', {
        'card': repetition.card,
        'repetition': repetition,
        'due_count': due_repetitions.count(),
    })


# === СТРАНИЦА ПРОГРЕССА ===

def progress_view(request: HttpRequest) -> HttpResponse:
    """
    Страница прогресса по карточкам.
    Работает по TelegramUser из сессии, без Django-авторизации.
    """
    tg_user = get_tg_user(request)
    if not tg_user:
        return render(request, 'progress.html', {
            'error': 'Пожалуйста, откройте сайт по ссылке из Telegram-бота.',
            'stats_by_level': {},
            'due_cards': 0,
        })

    current_difficulty = request.GET.get('difficulty')
    all_user_cards = Card.objects.filter(owner=tg_user)

    cards = all_user_cards
    if current_difficulty:
        cards = cards.filter(difficulty=current_difficulty)

    diff_counts = all_user_cards.values('difficulty').annotate(total=Count('difficulty'))
    counts_dict = {item['difficulty']: item['total'] for item in diff_counts}

    stats = {
        'beginner': {'label': 'Начальный', 'count': counts_dict.get('beginner', 0)},
        'intermediate': {'label': 'Средний', 'count': counts_dict.get('intermediate', 0)},
        'advanced': {'label': 'Продвинутый', 'count': counts_dict.get('advanced', 0)},
    }

    due_count = Repetition.objects.filter(
        card__owner=tg_user,
        next_review__lte=timezone.now()
    ).count()

    return render(request, 'progress.html', {
        'stats_by_level': stats,
        'due_cards': due_count,
        'current_difficulty': current_difficulty,
        'cards': cards,
    })


# === СТРАНИЦА НАСТРОЕК ===

def settings_view(request: HttpRequest) -> HttpResponse:
    """
    Настройки интервального повторения и параметров голоса для TelegramUser.
    """
    tg_user = get_tg_user(request)
    if not tg_user:
        return render(request, 'settings.html', {
            'error': 'Пожалуйста, откройте сайт по ссылке из Telegram-бота.'
        })

    settings_obj, _ = UserSettings.objects.get_or_create(user=tg_user)

    if request.method == 'POST':
        settings_obj.first_interval = int(request.POST.get('first_interval', settings_obj.first_interval))
        settings_obj.second_interval = int(request.POST.get('second_interval', settings_obj.second_interval))
        settings_obj.interval_multiplier = float(request.POST.get('interval_multiplier', settings_obj.interval_multiplier))
        settings_obj.max_interval = int(request.POST.get('max_interval', settings_obj.max_interval))
        settings_obj.min_easiness = float(request.POST.get('min_easiness', settings_obj.min_easiness))
        settings_obj.voice_gender = request.POST.get('voice_gender', settings_obj.voice_gender)
        settings_obj.save()
        return HttpResponseRedirect(reverse('settings') + '?saved=1')

    return render(request, 'settings.html', {'settings': settings_obj, 'saved': request.GET.get('saved')})


# === СТРАНИЦА ТЕСТА ===

# def test_view(request: HttpRequest) -> HttpResponse:
#     """
#     Страница 'Тест': показывает случайную карточку текущего пользователя.
#     Ожидает telegram_id в сессии (устанавливается в bot_login_view).
#     """
#     tg_user = get_tg_user(request)
#     if not tg_user:
#         return HttpResponse("Пользователь не найден. Откройте сайт по ссылке из бота.")
#
#     cards_qs = Card.objects.filter(owner=tg_user)
#     if not cards_qs.exists():
#         return HttpResponse("У вас пока нет карточек для теста.")
#
#     card = choice(list(cards_qs))
#
#     return render(request, "test.html", {"card": card})




from random import choice
import re

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from words.models import Word


def test_view(request: HttpRequest) -> HttpResponse:
    """
    Тест по словам (Word) с шаблоном test_page.html.
    - GET: показывает случайное слово и его картинку (если есть).
    - POST: проверяет перевод пользователя, показывает результат и новое слово.
    """
    words = Word.objects.all()
    if not words.exists():
        return render(request, 'test_page.html', {
            'word': None,
            'message': 'Нет слов для теста.',
        })

    if request.method == 'POST':
        word_id = request.POST.get('word_id')
        user_translation_raw = request.POST.get('translation', '').strip()
        user_translation = re.sub(r'[^\w\s]', '', user_translation_raw.lower())

        try:
            word = Word.objects.get(pk=word_id)
        except Word.DoesNotExist:
            return render(request, 'test_page.html', {
                'word': choice(list(words)),
                'message': 'Ошибка: слово не найдено.',
            })

        is_correct = user_translation == word.translation.strip().lower()

        context = {
            # Новое случайное слово для следующего вопроса
            'word': choice(list(words)),

            # Результат по предыдущему слову
            'result': 'correct' if is_correct else 'incorrect',
            'previous_word': word.text,
            'correct_translation': word.translation,
            'user_translation': user_translation_raw,
        }
        return render(request, 'test_page.html', context)

    # GET — первый показ
    context = {
        'word': choice(list(words)),
    }
    return render(request, 'test_page.html', context)


# === API ДЛЯ РЕГИСТРАЦИИ ПОЛЬЗОВАТЕЛЯ ИЗ БОТА ===

@api_view(['POST'])
def register_user(request):
    """
    API для регистрации пользователя через бота.
    """
    telegram_id = request.data.get('telegram_id')
    username = request.data.get('username')

    if not telegram_id:
        return Response({'error': 'telegram_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    user, created = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={'username': username}
    )

    if created:
        return Response({'status': 'created'}, status=status.HTTP_201_CREATED)
    else:
        return Response({'status': 'exists'}, status=status.HTTP_200_OK)
