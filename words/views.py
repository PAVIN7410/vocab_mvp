# words/views.py
import io
import json
import logging
import random
from io import BytesIO

from deep_translator import GoogleTranslator
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    UpdateView,
    DeleteView
)
from django.views.generic.edit import CreateView
from django.views.generic.list import ListView
from gtts import gTTS
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from vocab.models import Repetition
from vocab.models import TelegramUser, Card
from vocab.models import UserSettings
from vocab.utils import get_tg_user
from words.models import Word

logger = logging.getLogger(__name__)


def register_user(request):
    if request.method == 'POST':
        telegram_id = request.POST.get('telegram_id')
        username = request.POST.get('username')

        user, created = TelegramUser.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={'username': username}
        )

        if created:
            return JsonResponse({'status': 'created'})
        else:
            return JsonResponse({'status': 'exists'})
    return JsonResponse({'error': 'Invalid method'}, status=405)


def test_view(request):
    # Получаем все слова
    words = Word.objects.all()
    if not words.exists():
        return render(request, 'test_page.html', {'message': 'No words available. Please add words first.'})

    result = None
    previous_word = None
    previous_word_id = None
    correct_translation = None
    user_translation = None

    # Обработка ответа пользователя
    if request.method == 'POST':
        word_id = request.POST.get('word_id')
        user_translation = request.POST.get('translation', '').strip().lower()

        # Находим слово, которое проверяли
        prev_word_obj = get_object_or_404(Word, id=word_id)
        correct_answer = prev_word_obj.translation.strip().lower()

        previous_word = prev_word_obj.text
        previous_word_id = prev_word_obj.id
        correct_translation = prev_word_obj.translation

        if user_translation == correct_answer:
            result = 'correct'
        else:
            result = 'incorrect'

        # Выбираем НОВОЕ слово для следующего раунда
        current_word = random.choice(words)

        context = {
            'word': current_word,
            'result': result,
            'previous_word': previous_word,
            'previous_word_id': previous_word_id,
            'correct_translation': correct_translation,
            'user_translation': user_translation,
        }

        return render(request, 'test_page.html', context)


    if words.exists():
        word = random.choice(words)
        # Вызываем проверку/генерацию
        get_or_generate_image(word)

        # ... (ваш текущий контекст) ...
        return render(request, 'test_page.html', context)


class RegisterUser(APIView):
    def post(self, request):
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


def home(request):
    return render(request, 'words/home.html')


# --- CRUD ---

class WordListView(LoginRequiredMixin, ListView):
    model = Word
    template_name = 'word_list.html'
    context_object_name = 'words'

    def get_queryset(self):
        tg_user = get_tg_user(self.request)
        if tg_user:
            qs = Word.objects.filter(user=tg_user).order_by('-id')

            return qs
        # Если нет пользователя — показываем все слова
        return Word.objects.all().order_by('-id')


class WordCreateView(LoginRequiredMixin, CreateView):
    model = Word
    fields = ['text', 'translation']
    template_name = 'word_form.html'
    success_url = reverse_lazy('word-list')

    def form_valid(self, form):
        # Получаем пользователя перед сохранением
        tg_user = get_tg_user(self.request)

        if not tg_user:
            from django.contrib import messages
            messages.error(self.request, 'Ошибка авторизации. Войдите через бота.')
            return redirect('word-list')

        # ПРИВЯЗЫВАЕМ К ПОЛЬЗОВАТЕЛЮ ДО СОХРАНЕНИЯ
        form.instance.user = tg_user
        form.instance.source_lang = 'en'

        # Автоперевод
        if not form.instance.translation and form.instance.text:
            try:
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source='auto', target='ru').translate(form.instance.text)
                if translated:
                    form.instance.translation = str(translated)
            except Exception as e:
                print(f"Translation error: {e}")

        response = super().form_valid(form)

        # Создаём карточку
        Card.objects.get_or_create(
            owner=tg_user,
            word=form.instance.text,
            defaults={
                'translation': form.instance.translation,
                'difficulty': 'beginner',
            }
        )

        return response

# --- Добавляем UpdateView ---
class WordUpdateView(LoginRequiredMixin, UpdateView):
    model = Word
    fields = ['text', 'translation']
    template_name = 'word_form.html'
    success_url = reverse_lazy('word-list')

    def form_valid(self, form):
        """Обработчик успешной валидации формы."""

        # 1. Получаем пользователя
        tg_user = get_tg_user(self.request)

        # 2. Если нет пользователя — выводим ошибку
        if not tg_user:
            from django.contrib import messages
            messages.error(self.request, 'Ошибка авторизации.')
            return redirect('word-list')

        # 3. Проверяем дубликаты ПЕРЕД сохранением
        text = form.cleaned_data['text'].strip()
        translation = form.cleaned_data.get('translation', '').strip()

        if Word.objects.filter(text=text, translation=translation).exists():
            from django.contrib import messages
            messages.warning(self.request, f'Слово "{text}" уже существует в базе!')
            return self.render_to_response(self.get_context_data())

        # 4. Привязываем к пользователю
        form.instance.user = tg_user
        form.instance.source_lang = 'en'

        # 5. Автоперевод если не указан
        if not translation and text:
            try:
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source='auto', target='ru').translate(text)
                if translated:
                    form.instance.translation = str(translated)
                    print(f"✅ Автоперевод для '{text}': {translated}")
            except Exception as e:
                print(f"⚠️ Ошибка автоперевода: {e}")

        # 6. Сохраняем слово в БД
        response = super().form_valid(form)

        # 7. Создаём карточку ТОЛЬКО для владельца
        try:
            Card.objects.create(
                owner=tg_user,
                word=form.instance.text,
                translation=form.instance.translation,
                difficulty='beginner',
            )
            print(f"✅ Карточка создана для '{form.instance.text}'")
        except Exception as e:
            print(f"⚠️ Ошибка создания карточки: {e}")

        return response

@login_required
def progress_view(request):
    tg_user = getattr(request.user, 'tg_user', None)
    if not tg_user:
        return render(request, 'progress.html', {'error': 'Аккаунт не привязан к Telegram'})

    # Количество изученных слов
    total_cards = Card.objects.filter(owner=tg_user).count()

    # Средняя частота повторений
    avg_repeats = Repetition.objects.filter(card__owner=tg_user).aggregate(Avg('repeats'))['repeats__avg']

    # Статистика по уровням сложности
    levels_stats = Card.objects.filter(owner=tg_user).values('difficulty').annotate(count=Count('id'))

    context = {
        'total_cards': total_cards,
        'average_repeats': round(float(avg_repeats), 2) if avg_repeats else 0,
        'levels_stats': dict(levels_stats),
    }
    return render(request, 'progress.html', context)




# --- Добавляем DeleteView ---
class WordDeleteView(LoginRequiredMixin, DeleteView):
    model = Word
    template_name = 'word_confirm_delete.html'
    success_url = reverse_lazy('word-list')


@csrf_exempt
def translate_word(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    text = data.get('text', '').strip()
    if not text:
        return JsonResponse({'error': 'Text is required'}, status=400)

    def has_cyrillic(t):
        return any('а' <= c.lower() <= 'я' or c.lower() == 'ё' for c in t)

    def has_latin(t):
        return any('a' <= c.lower() <= 'z' for c in t)

    is_cyrillic = has_cyrillic(text)
    is_latin = has_latin(text)

    if is_cyrillic and not is_latin:
        src, dest = 'ru', 'en'
    elif is_latin and not is_cyrillic:
        src, dest = 'en', 'ru'
    else:
        src, dest = 'en', 'ru'

    try:
        # Используем GoogleTranslator вместо гигачата
        translated = GoogleTranslator(source=src, target=dest).translate(text)
    except Exception as e:
        logger.exception("Deep Translate failed")
        return JsonResponse({'error': f'Translation failed: {e}'}, status=500)


    return JsonResponse({
        'translation': translated,
        'source_lang': src,
        'dest_lang': dest,
    })




def generate_audio(request, pk, text_type='word'):
    word = get_object_or_404(Word, pk=pk)

    # Выбираем текст
    if text_type == 'word':
        text = word.text
    else:
        text = word.translation

    text = text.strip()
    if not text:
        return HttpResponse("Пустой текст", status=400)

    # Определяем язык
    def detect_language(text):
        text = text.lower()
        if any('а' <= c <= 'я' or c == 'ё' for c in text):
            return 'ru'
        if any('a' <= c <= 'z' for c in text):
            return 'en'
        return 'en'

    lang = detect_language(text)

    try:
        tts = gTTS(text=text, lang=lang)
        audio_io = BytesIO()
        tts.write_to_fp(audio_io)
        audio_io.seek(0)

        response = HttpResponse(audio_io.read(), content_type='audio/mpeg')
        response['Content-Disposition'] = f'inline; filename="{text_type}.mp3"'
        return response
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return HttpResponse(f"Ошибка TTS: {e}", status=500)



def speak_text(request):
    """
    Озвучивает любой текст (для формы добавления слова)
    Пример: /words/speak/?text=hello&lang=en
    """
    text = request.GET.get('text', '').strip()
    lang = request.GET.get('lang', 'en')  # по умолчанию английский

    if not text:
        return HttpResponse(status=400)

    # Определяем язык по тексту, если не указан
    if lang == 'auto':
        lang = 'ru' if any('а' <= c.lower() <= 'я' or c.lower() == 'ё' for c in text) else 'en'

    try:
        # Создаём аудио
        tts = gTTS(text=text, lang=lang)
        audio_io = io.BytesIO()
        tts.write_to_fp(audio_io)
        audio_io.seek(0)

        # Отправляем как MP3
        response = HttpResponse(audio_io, content_type='audio/mpeg')
        response['Content-Disposition'] = 'inline'
        return response
    except Exception as e:
        return HttpResponse(status=500)


@login_required  # ← Обязательно требуем авторизацию
def settings_view(request):
    # ✅ Берём РЕАЛЬНОГО пользователя из запроса
    tg_user = getattr(request, 'tg_user', None)

    # Если связи нет, создаём её (для совместимости)
    if not tg_user:
        tg_user, _ = TelegramUser.objects.get_or_create(
            user=request.user,
            defaults={
                'telegram_id': f"web_{request.user.id}",
                'username': request.user.username
            }
        )
        request.tg_user = tg_user

    # ✅ Получаем настройки для ЭТОГО пользователя
    settings, _ = UserSettings.objects.get_or_create(user=tg_user)

    if request.method == 'POST':
        settings.first_interval = int(request.POST.get('first_interval', settings.first_interval))
        settings.second_interval = int(request.POST.get('second_interval', settings.second_interval))
        settings.interval_multiplier = float(request.POST.get('interval_multiplier', settings.interval_multiplier))
        settings.max_interval = int(request.POST.get('max_interval', settings.max_interval))
        settings.min_easiness = float(request.POST.get('min_easiness', settings.min_easiness))
        settings.voice_gender = request.POST.get('voice_gender', settings.voice_gender)
        settings.save()
        return HttpResponseRedirect(reverse('settings') + '?saved=1')

    return render(request, 'settings.html', {
        'settings': settings,
        'saved': request.GET.get('saved')
    })