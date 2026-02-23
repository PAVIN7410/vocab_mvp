# bot/voice.py
import tempfile
import time

from gtts import gTTS


def synthesize_text_to_mp3(
    text: str,
    lang: str = "en",
    tld: str = "com",
    slow: bool = False,
    retries: int = 2,
    delay: float = 1.5,
) -> str:
    """
    Генерирует MP3-файл озвучки текста и возвращает путь к файлу.
    Делает несколько попыток при сетевых ошибках.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tts = gTTS(text=text, lang=lang, tld=tld, slow=slow)
                tts.save(tf.name)
                return tf.name
        except Exception as e:
            last_err = e
            # Лёгкий лог в консоль, чтобы видеть, что была ошибка и ретрай
            print(f"TTS error on attempt {attempt + 1}: {e}")
            time.sleep(delay)
    # Если все попытки не удались — отдадим ошибку наверх
    raise last_err


# Доступные акценты (по сути "голоса" gTTS) для разных языков.
VOICE_OPTIONS = {
    "en": {
        "com": "English (US)",
        "co.uk": "English (UK)",
        "com.au": "English (Australia)",
        "ca": "English (Canada)",
        "co.in": "English (India)",
    },
    "ru": {
        "com": "Russian",
    }
}


def get_available_voices():
    """
    Возвращает словарь доступных голосов/акцентов для использования в интерфейсе настроек.
    Структура:
    {
        'en': {'com': 'English (US)', 'co.uk': 'English (UK)', ...},
        'ru': {'com': 'Russian'},
        ...
    }
    """
    return VOICE_OPTIONS
