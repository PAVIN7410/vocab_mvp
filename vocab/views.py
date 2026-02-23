# vocab/views.py
import logging
import re
from random import choice

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from words.models import Word
from .models import TelegramUser, Card, Repetition, UserSettings
from .serializers import CardSerializer

logger = logging.getLogger(__name__)


# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ЮЗЕРА ===
def get_tg_user(request):
    try:
        return request.user.telegramuser
    except (ObjectDoesNotExist, AttributeError):
        return None


# === СТРАНИЦА ПРОГРЕССА ===
@login_required
def progress_view(request):
    tg_user = get_tg_user(request)
    if not tg_user:
        return render(request, 'progress.html',
                      {'error': 'Аккаунт не связан с Telegram.', 'stats_by_level': {}, 'due_cards': 0})

    current_difficulty = request.GET.get('difficulty')

    # Базовый набор карточек пользователя
    all_user_cards = Card.objects.filter(owner=tg_user)

    # Фильтруем список для вывода (если в шаблоне есть цикл {% for card in cards %})
    cards = all_user_cards
    if current_difficulty:
        cards = cards.filter(difficulty=current_difficulty)

    # Собираем статистику (оптимизировано через annotate)
    diff_counts = all_user_cards.values('difficulty').annotate(total=Count('difficulty'))
    counts_dict = {item['difficulty']: item['total'] for item in diff_counts}

    stats = {
        'beginner': {'label': 'Начальный', 'count': counts_dict.get('beginner', 0)},
        'intermediate': {'label': 'Средний', 'count': counts_dict.get('intermediate', 0)},
        'advanced': {'label': 'Продвинутый', 'count': counts_dict.get('advanced', 0)},
    }

    # Считаем карточки для повторения
    due_count = Repetition.objects.filter(
        card__owner=tg_user,
        next_review__lte=timezone.now()
    ).count()

    return render(request, 'progress.html', {
        'stats_by_level': stats,
        'due_cards': due_count,
        'current_difficulty': current_difficulty,
        'cards': cards
    })


# === СТРАНИЦА ПОВТОРЕНИЯ ===
@login_required
def review_view(request):
    tg_user = get_tg_user(request)
    if not tg_user:
        return render(request, 'review.html', {'error': 'Пользователь не найден.'})

    due_repetitions = Repetition.objects.filter(
        card__owner=tg_user,
        next_review__lte=timezone.now()
    ).select_related('card').order_by('next_review')

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
        'due_count': due_repetitions.count()
    })


# === СТРАНИЦА НАСТРОЕК ===
@login_required
def settings_view(request):
    tg_user = get_tg_user(request)
    if not tg_user:
        return render(request, 'settings.html', {'error': 'Сначала привяжите Telegram.'})

    settings, _ = UserSettings.objects.get_or_create(user=tg_user)

    if request.method == 'POST':
        settings.first_interval = int(request.POST.get('first_interval', settings.first_interval))
        settings.second_interval = int(request.POST.get('second_interval', settings.second_interval))
        settings.interval_multiplier = float(request.POST.get('interval_multiplier', settings.interval_multiplier))
        settings.max_interval = int(request.POST.get('max_interval', settings.max_interval))
        settings.min_easiness = float(request.POST.get('min_easiness', settings.min_easiness))
        # --- НОВОЕ: Сохраняем пол голоса ---
        settings.voice_gender = request.POST.get('voice_gender', settings.voice_gender)
        settings.save()
        return HttpResponseRedirect(reverse('settings') + '?saved=1')

    return render(request, 'settings.html', {'settings': settings, 'saved': request.GET.get('saved')})


# === API И ТЕСТЫ (ОСТАВЛЕНО БЕЗ ИЗМЕНЕНИЙ) ===
def test_view(request):
    words = Word.objects.all()
    if not words.exists():
        return render(request, 'test_page.html', {'message': 'Нет слов.'})

    if request.method == 'POST':
        word_id = request.POST.get('word_id')
        user_translation = re.sub(r'[^\w\s]', '', request.POST.get('translation', '').strip().lower())
        try:
            word = Word.objects.get(pk=word_id)
            is_correct = user_translation == word.translation.strip().lower()
            return render(request, 'test_page.html', {
                'word': choice(list(words)),
                'result': 'correct' if is_correct else 'incorrect',
                'previous_word': word.text,
                'correct_translation': word.translation,
                'user_translation': request.POST.get('translation', '').strip()
            })
        except Word.DoesNotExist:
            return render(request, 'test_page.html', {'word': choice(list(words)), 'error': 'Ошибка.'})

    return render(request, 'test_page.html', {'word': choice(list(words))})

@api_view(['POST'])
def register_user(request):
    """
    API для регистрации пользователя через бота
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

