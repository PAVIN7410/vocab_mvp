### words/views.py
import io
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)
from django.shortcuts import get_object_or_404
from io import BytesIO
import logging
from .models import Word
from django.urls import reverse_lazy
from gtts import gTTS
from django.http import HttpResponse
from django.shortcuts import render
import random
from .models import Word
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from googletrans import Translator
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from vocab.models import TelegramUser

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
    words = Word.objects.all()
    if words.exists():
        word = random.choice(words)
        return render(request, 'test_page.html', {'word': word.text})
    else:
        return render(request, 'test_page.html', {'message': 'No words available. Please add words first.'})





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
        # Получаем или создаем тестового пользователя
        from vocab.models import TelegramUser
        test_user, created = TelegramUser.objects.get_or_create(
            telegram_id=12345,  # Тестовый ID
            defaults={'username': 'test_user'}
        )
        form.instance.user = test_user
        
        # Переводим автоматически, если перевод пустой
        if not form.instance.translation and form.instance.text:
            try:
                translator = Translator()
                translation = translator.translate(form.instance.text, src='en', dest='ru')
                form.instance.translation = translation.text
            except Exception:
                pass  # Если перевод не удался, оставляем как есть
        
        return super().form_valid(form)


class WordUpdateView(UpdateView):
    model = Word
    fields = ['text', 'translation']
    template_name = 'word_form.html'
    success_url = reverse_lazy('word-list')


class WordDeleteView(DeleteView):
    model = Word
    success_url = '/words/'
    template_name = 'word_confirm_delete.html'


@csrf_exempt
def translate_word(request):
    """АPI endpoint для перевода слов"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        # Парсим JSON данные
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
        text = data.get('text', '').strip()
        
        # Проверки
        if not text:
            return JsonResponse({'error': 'Text is required'}, status=400)
            
        if len(text) > 1000:
            return JsonResponse({'error': 'Text too long (max 1000 characters)'}, status=400)
            
        if not any(c.isalpha() for c in text):
            return JsonResponse({'error': 'Text should contain letters'}, status=400)
        
        print(f"[DEBUG] Translating text: '{text}'")  # Отладка
        
        translator = Translator()
        
        # Проверяем, содержит ли текст кириллицу
        def has_cyrillic(text):
            return bool([c for c in text if '\u0430' <= c.lower() <= '\u044f' or c.lower() in 'ёщ'])
        
        def has_latin(text):
            return bool([c for c in text if 'a' <= c.lower() <= 'z'])
        
        # Определяем язык по алфавиту в первую очередь
        is_cyrillic = has_cyrillic(text)
        is_latin = has_latin(text)
        
        print(f"[DEBUG] Text analysis - Cyrillic: {is_cyrillic}, Latin: {is_latin}")
        
        # Определяем направление перевода
        if is_cyrillic and not is_latin:
            # Кириллица -> считаем русским -> переводим на английский
            print(f"[DEBUG] Treating as Russian (Cyrillic detected)")
            translation = translator.translate(text, src='ru', dest='en')
        elif is_latin and not is_cyrillic:
            # Латиница -> считаем английским -> переводим на русский
            print(f"[DEBUG] Treating as English (Latin detected)")
            translation = translator.translate(text, src='en', dest='ru')
        else:
            # Неопределенный случай -> используем Google автоопределение
            print(f"[DEBUG] Using Google auto-detection as fallback")
            detection = translator.detect(text)
            detected_lang = detection.lang
            print(f"[DEBUG] Google detected language: {detected_lang}")
            
            if detected_lang in ['ru', 'bg', 'uk']:  # славянские языки
                translation = translator.translate(text, src='ru', dest='en')
            elif detected_lang in ['en']:
                translation = translator.translate(text, src='en', dest='ru')
            else:
                # По умолчанию переводим на русский
                translation = translator.translate(text, dest='ru')
        
        if translation and translation.text:
            result = {
                'translation': translation.text,
                'source_lang': translation.src,
                'dest_lang': translation.dest
            }
            print(f"[DEBUG] Translation result: {result}")  # Отладка
            return JsonResponse(result)
        else:
            return JsonResponse({'error': 'Translation returned empty result'}, status=500)
            
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Translation failed: {error_msg}")  # Отладка
        
        # Пробуем альтернативный способ
        try:
            translator = Translator(service_urls=['translate.google.com', 'translate.google.co.kr'])
            translation = translator.translate(text, src='auto', dest='ru')
            return JsonResponse({
                'translation': translation.text,
                'source_lang': translation.src,
                'dest_lang': translation.dest,
                'note': 'Used fallback translation service'
            })
        except Exception as fallback_error:
            print(f"[ERROR] Fallback translation also failed: {str(fallback_error)}")
            return JsonResponse({
                'error': f'Translation service unavailable: {error_msg}',
                'fallback_error': str(fallback_error),
                'suggestion': 'Please check your internet connection and try again'
            }, status=500)



logger = logging.getLogger(__name__)

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


