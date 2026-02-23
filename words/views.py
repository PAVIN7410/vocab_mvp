# words/views.py
import io
import json
import logging
import random
from io import BytesIO

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)
from gtts import gTTS
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from vocab.deep_translate import GoogleTranslator
from vocab.models import TelegramUser
from vocab.utils import get_or_generate_image
from .models import Word

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
class WordListView(ListView):
    model = Word
    template_name = 'word_list.html'
    context_object_name = 'words'


class WordDetailView(DetailView):
    model = Word
    template_name = 'word_detail.html'


class WordCreateView(CreateView):
    model = Word
    fields = ['text', 'translation']
    template_name = 'word_form.html'
    success_url = reverse_lazy('word-list')
    
    def form_valid(self, form):
        # 1. Импортируем модель (убедитесь, что имя НЕ совпадает с переменной ниже)
        from vocab.models import TelegramUser as TelegramUserModel

        # 2. Получаем ОБЪЕКТ (экземпляр), а не класс
        # get_or_create возвращает кортеж (объект, создано_ли_оно)
        user_instance, _ = TelegramUserModel.objects.get_or_create(
            telegram_id=12345,
            defaults={'username': 'test_user'}
        )

        # 3. Присваиваем именно ОБЪЕКТ экземпляру слова
        form.instance.user = user_instance

        # 4. Логика перевода
        if not form.instance.translation and form.instance.text:
            try:
                from deep_translator import GoogleTranslator
                translated = GoogleTranslator(source='en', target='ru').translate(form.instance.text)
                if translated:
                    form.instance.translation = str(translated)
            except Exception as e:
                print(f"Translation error: {e}")

        # 5. Сохраняем
        return super().form_valid(form)



# --- Добавляем UpdateView ---
class WordUpdateView(UpdateView):
    model = Word
    fields = ['text', 'translation']
    template_name = 'word_form.html'
    success_url = reverse_lazy('word-list')

#     def form_valid(self, form):
#         # Сохраняем без изменений пользователя
#         return super().form_valid(form)


# --- Добавляем DeleteView ---
class WordDeleteView(DeleteView):
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
        print(f"Ошибка TTS: {e}")
        return HttpResponse(status=500)


def settings_view(request):
    try:
        telegram_user = TelegramUser.objects.get(telegram_id=12345)
    except TelegramUser.DoesNotExist:
        telegram_user = TelegramUser.objects.create(
            telegram_id=12345,
            username='test_user'
        )

    settings, _ = UserSettings.objects.get_or_create(user=telegram_user)

    if request.method == 'POST':
        settings.first_interval = int(request.POST.get('first_interval', settings.first_interval))
        settings.second_interval = int(request.POST.get('second_interval', settings.second_interval))
        settings.interval_multiplier = float(request.POST.get('interval_multiplier', settings.interval_multiplier))
        settings.max_interval = int(request.POST.get('max_interval', settings.max_interval))
        settings.min_easiness = float(request.POST.get('min_easiness', settings.min_easiness))
        settings.voice_gender = request.POST.get('voice_gender', settings.voice_gender)  # Сохраняем выбор голоса
        settings.save()
        return HttpResponseRedirect(reverse('settings') + '?saved=1')

    return render(request, 'settings.html', {
        'settings': settings,
        'saved': request.GET.get('saved')
    })
