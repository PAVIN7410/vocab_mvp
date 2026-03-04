# bot/image_generator.py
import urllib.parse
import requests
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

def fetch_image_for_word(word: str, translation: str | None = None) -> File | None:
    """
    Пытается получить картинку через Pollinations по слову/переводу.
    Возвращает Django File, готовый для ImageField, либо None при ошибке.
    """
    # Собираем понятный prompt
    if translation:
        prompt = f"{word} ({translation})"
    else:
        prompt = word
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_BASE}/{encoded_prompt}"
    print(f"[Pollinations] Запрос изображения: {url}")
    try:
        resp = requests.get(url, timeout=40)
        resp.raise_for_status()
    except requests.RequestException as e:
        # НЕ бросаем исключение наружу, только логируем
        print(f"[Pollinations] Ошибка запроса: {e}")
        return None
    img_temp = NamedTemporaryFile(delete=True)
    img_temp.write(resp.content)
    img_temp.flush()
    return File(img_temp, name="pollinations_image.jpg")
