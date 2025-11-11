# vocab/views.py
from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render
from django.utils import timezone
from django.http import HttpResponse
from .models import TelegramUser, Card, Repetition
from words.models import Word
from .serializers import TelegramUserSerializer, CardSerializer
from gtts import gTTS
from random import choice
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.contrib.auth.models import User
import logging
from io import BytesIO
import re

# Настройка логирования

logger = logging.getLogger(__name__)

# === ОСНОВНОЙ ВЬЮХА ТЕСТА ===
def test_view(request):
    """Страница теста - показывает случайное слово и проверяет ответ"""
    words = Word.objects.all()
    if not words.exists():
        return render(request, 'test_page.html', {
            'message': 'Нет доступных слов для тестирования.'
        })

    if request.method == 'POST':
        word_id = request.POST.get('word_id')
        user_translation = request.POST.get('translation', '').strip().lower()

        # Очищаем от лишнего: пробелы, регистр, пунктуация
        user_translation = re.sub(r'[^\w\s]', '', user_translation).strip().lower()

        try:
            word = Word.objects.get(pk=word_id)
            correct_translation = word.translation.strip().lower()
            is_correct = user_translation == correct_translation

            # Новое случайное слово для следующего теста
            next_word = choice(list(words))

            return render(request, 'test_page.html', {
                'word': next_word,
                'result': 'correct' if is_correct else 'incorrect',
                'previous_word': word.text,
                'correct_translation': word.translation,
                'user_translation': request.POST.get('translation', '').strip()
            })
        except Word.DoesNotExist:
            logger.error(f"Word with id {word_id} does not exist")
            return render(request, 'test_page.html', {
                'word': choice(list(words)),
                'error': 'Слово не найдено.'
            })

    # GET-запрос — показываем случайное слово
    word = choice(list(words))
    return render(request, 'test_page.html', {'word': word})



@api_view(['POST'])
def register_user(request):
    telegram_id = request.data.get('telegram_id')
    username = request.data.get('username')

    user, created = TelegramUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={'username': username}
    )

    if created:
        return Response({'status': 'created'}, status=status.HTTP_201_CREATED)
    else:
        return Response({'status': 'exists'}, status=status.HTTP_200_OK)



class RegisterTelegramUser(APIView):
    def post(self, request):
        telegram_id = request.data.get('telegram_id')
        username = request.data.get('username', '')
        if not telegram_id:
            return Response({'error': 'telegram_id required'}, status=400)
        user, created = TelegramUser.objects.get_or_create(telegram_id=telegram_id)
        user.username = username
        user.save()
        return Response({'status': 'OK'}, status=201 if created else 200)

class CardListCreateView(generics.ListCreateAPIView):
    serializer_class = CardSerializer

    def get_queryset(self):
        telegram_id = self.request.query_params.get('telegram_id')
        return Card.objects.filter(owner__telegram_id=telegram_id)

    def perform_create(self, serializer):
        telegram_id = self.request.data.get('telegram_id')
        owner = TelegramUser.objects.get(telegram_id=telegram_id)
        serializer.save(owner=owner)


# @login_required
def progress_view(request):
    # try:
    #     telegram_user = request.user.telegramuser
    # except TelegramUser.DoesNotExist:
    #     return render(request, 'progress.html', {'error': 'Пользователь не найден.'})
    """
    Статистика по карточкам — без авторизации (для теста)
    """
    # Временно используем тестового TelegramUser
    try:
        telegram_user = TelegramUser.objects.get(telegram_id=12345)
    except TelegramUser.DoesNotExist:
        telegram_user = TelegramUser.objects.create(
            telegram_id=12345,
            username='test_user'
        )

    # Общая статистика
    total_cards = Card.objects.filter(owner=telegram_user).count()
    due_cards = Repetition.objects.filter(
        card__owner=telegram_user,
        next_review__lte=timezone.now()
    ).count()

    # По уровням сложности
    difficulty_stats = Card.objects.filter(owner=telegram_user).values('difficulty').annotate(
        count=Count('difficulty')
    )

    # Словарь для удобства
    difficulty_labels = dict(Card.DIFFICULTY_CHOICES)
    stats_by_level = {}
    for item in difficulty_stats:
        level = item['difficulty']
        stats_by_level[level] = {
            'label': difficulty_labels.get(level, level),
            'count': item['count']
        }

    # Заполняем нули для отсутствующих уровней
    for level_key, level_label in Card.DIFFICULTY_CHOICES:
        if level_key not in stats_by_level:
            stats_by_level[level_key] = {'label': level_label, 'count': 0}

    return render(request, 'progress.html', {
        'total_cards': total_cards,
        'due_cards': due_cards,
        'stats_by_level': stats_by_level,
    })



#@login_required
def review_view(request):
    """
    Просмотр слов для повторения (алгоритм SM-2)
    """
    # try:
    #     telegram_user = request.user.telegramuser
    # except TelegramUser.DoesNotExist:
    #     return render(request, 'review.html', {
    #         'error': 'Пользователь не найден в боте.'
    #     })

    # Временно используем тестового пользователя
    try:
        # Пытаемся найти TelegramUser с telegram_id=12345
        telegram_user = TelegramUser.objects.get(telegram_id=12345)
    except TelegramUser.DoesNotExist:
        # Или создаём
        telegram_user = TelegramUser.objects.create(
            telegram_id=12345,
            username='test_user'
        )



    # Находим карточки, которые пора повторять
    due_repetitions = Repetition.objects.filter(
        card__owner=telegram_user,
        next_review__lte=timezone.now()
    ).select_related('card').order_by('next_review')

    if not due_repetitions.exists():
        return render(request, 'review.html', {
            'message': 'Нет слов для повторения. Молодец!'
        })

    # Берём первую карточку
    repetition = due_repetitions.first()
    card = repetition.card

    if request.method == 'POST':
        # Получаем оценку пользователя
        quality = int(request.POST.get('quality', 3))  # 1-плохо, 2-трудно, 3-хорошо, 4-отлично

        # Обновляем интервал по SM-2
        repetition.schedule_review(quality)

        # Перенаправляем на следующее слово
        return HttpResponseRedirect(reverse('review'))

    return render(request, 'review.html', {
        'card': card,
        'repetition': repetition,
        'due_count': due_repetitions.count()
    })




