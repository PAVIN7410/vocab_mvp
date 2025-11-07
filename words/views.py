def test_view(request):
    words = Word.objects.all()
    if words.exists():
        word = random.choice(words)
        return render(request, 'test_page.html', {'word': word.text})
    else:
        return render(request, 'test_page.html', {'message': 'No words available. Please add words first.'})

# words/views.py
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView
)
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
from .models import TelegramUser
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


def tts_view(request, pk):
    word = Word.objects.get(pk=pk)
    return JsonResponse({'text': word.text})


def word_audio_view(request, pk):
    """Генерирует аудио для слова"""
    try:
        word = Word.objects.get(pk=pk)
        
        # Используем сохраненный язык, если есть
        if hasattr(word, 'source_lang') and word.source_lang:
            lang = word.source_lang
        else:
            # Определяем язык по символам
            def has_cyrillic(text):
                return bool([c for c in text if 'а' <= c.lower() <= 'я' or c.lower() in 'ёщ'])
            
            lang = 'ru' if has_cyrillic(word.text) else 'en'
        
        # Генерируем аудио
        tts = gTTS(text=word.text, lang=lang)
        
        # Создаем HTTP response с аудио
        response = HttpResponse(content_type='audio/mpeg')
        tts.write_to_fp(response)
        return response
        
    except Word.DoesNotExist:
        return HttpResponse('Слово не найдено', status=404)
    except Exception as e:
        return HttpResponse(f'Ошибка: {str(e)}', status=500)


def word_translation_audio_view(request, pk):
    """Генерирует аудио для перевода слова"""
    try:
        word = Word.objects.get(pk=pk)
        
        # Определяем язык перевода (противоположный оригиналу)
        if hasattr(word, 'source_lang') and word.source_lang:
            trans_lang = 'ru' if word.source_lang == 'en' else 'en'
        else:
            def has_cyrillic(text):
                return bool([c for c in text if 'а' <= c.lower() <= 'я' or c.lower() in 'ёщ'])
            
            # Если оригинал на русском, перевод на английском
            trans_lang = 'en' if has_cyrillic(word.text) else 'ru'
        
        # Генерируем аудио
        tts = gTTS(text=word.translation, lang=trans_lang)
        
        # Создаем HTTP response с аудио
        response = HttpResponse(content_type='audio/mpeg')
        tts.write_to_fp(response)
        return response
        
    except Word.DoesNotExist:
        return HttpResponse('Слово не найдено', status=404)
    except Exception as e:
        return HttpResponse(f'Ошибка: {str(e)}', status=500)


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


def generate_audio(request, pk):
    """Генерирует аудио файл для произношения слова"""
    try:
        word = Word.objects.get(pk=pk)
        
        # Получаем параметры из запроса
        requested_lang = request.GET.get('lang', 'en')  # язык с фронтенда
        text_type = request.GET.get('type', 'word')  # word или translation
        tld = request.GET.get('tld', 'com')  # для разных акцентов
        
        # Определяем текст для озвучивания
        if text_type == 'translation':
            text_to_speak = word.translation
        else:
            text_to_speak = word.text
            
        # Проверяем язык по содержимому текста
        def has_cyrillic(text):
            return bool([c for c in text if 'а' <= c.lower() <= 'я' or c.lower() in 'ёщ'])
        
        # Определяем правильный язык на основе содержимого
        if has_cyrillic(text_to_speak):
            actual_lang = 'ru'
        else:
            actual_lang = 'en'
            
        print(f"[DEBUG AUDIO] Text: '{text_to_speak}', Requested lang: {requested_lang}, Actual lang: {actual_lang}")
            
        from bot.voice import synthesize_text_to_mp3_advanced
        
        # Генерируем аудио с правильным языком
        audio_path = synthesize_text_to_mp3_advanced(text_to_speak, lang=actual_lang, tld=tld)
        
        # Открываем файл и возвращаем как HTTP ответ
        with open(audio_path, 'rb') as audio_file:
            response = HttpResponse(audio_file.read(), content_type='audio/mpeg')
            response['Content-Disposition'] = f'attachment; filename="{text_to_speak[:20]}.mp3"'
            return response
            
    except Word.DoesNotExist:
        return JsonResponse({'error': 'Word not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Audio generation failed: {str(e)}'}, status=500)
    finally:
        # Удаляем временный файл
        if 'audio_path' in locals():
            import os
            if os.path.exists(audio_path):
                os.remove(audio_path)

