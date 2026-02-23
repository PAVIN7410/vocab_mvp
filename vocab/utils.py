#vocab/utils.py:
from io import BytesIO

import requests
from deep_translator import GoogleTranslator
from django.core.files import File


def universal_translate(text, src='en', dest='ru'):
    return GoogleTranslator(source=src, target=dest).translate(text)


DJANGO_API_URL = "http://127.0.0.1:8000/api/"  # пример, поправь под свой

def register_user(telegram_id, username):
    r = requests.post(
        f'{DJANGO_API_URL}register/',
        json={'telegram_id': telegram_id, 'username': username}
    )
    return r


from datetime import datetime, timedelta

def sm2(repetition, grade):
    # grade: 0-5, качество ответа, 5 — отлично
    if grade < 3:
        repetition.repetitions = 0
        repetition.interval = 1
    else:
        if repetition.repetitions == 0:
            repetition.interval = 1
        elif repetition.repetitions == 1:
            repetition.interval = 6
        else:
            repetition.interval = int(repetition.interval * repetition.easiness)
        repetition.repetitions += 1
    repetition.easiness += (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    if repetition.easiness < 1.3:
        repetition.easiness = 1.3
    repetition.next_review = datetime.now() + timedelta(days=repetition.interval)
    repetition.save()



def get_word_difficulty(word: str) -> str:
    w = word.strip().lower()
    if len(w) <= 4:
        return 'beginner'
    elif len(w) <= 7:
        return 'intermediate'
    else:
        return 'advanced'



def get_or_generate_image(instance):
    """
    Проверяет картинку у объекта (Word или Card).
    Если её нет — генерирует через Pollinations AI и сохраняет.
    """
    if instance.image:
        return instance.image.url

    try:
        prompt = f"minimalist 3d render of {instance.text}, educational flashcard style, white background"
        url = f"https://image.pollinations.ai{prompt}?width=512&height=512&nologo=true"

        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            file_name = f"{instance.text}.jpg"
            instance.image.save(file_name, File(BytesIO(response.content)), save=True)
            return instance.image.url
    except Exception as e:
        print(f"Ошибка генерации картинки: {e}")

    return None
