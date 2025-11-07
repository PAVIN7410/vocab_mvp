# bot/speech_recognition_helper.py
"""
Модуль для распознавания речи из голосовых сообщений Telegram
"""

import os
import speech_recognition as sr
import tempfile
import subprocess
import shutil


def convert_ogg_to_wav_ffmpeg(ogg_path: str, wav_path: str) -> bool:
    """
    Конвертирует OGG в WAV используя ffmpeg
    """
    try:
        # Проверяем, есть ли ffmpeg
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            return False
        
        # Конвертируем
        result = subprocess.run(
            [ffmpeg_path, '-i', ogg_path, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', wav_path, '-y'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


async def recognize_speech_from_ogg(ogg_file_path: str, language: str = "ru-RU") -> str:
    """
    Распознает речь из OGG файла (формат голосовых сообщений Telegram)
    
    Args:
        ogg_file_path: Путь к OGG файлу
        language: Язык распознавания ("ru-RU" или "en-US")
    
    Returns:
        Распознанный текст
    """
    recognizer = sr.Recognizer()
    wav_path = None
    
    try:
        # Создаем временный WAV файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
            wav_path = wav_file.name
        
        # Пробуем конвертировать с ffmpeg
        success = convert_ogg_to_wav_ffmpeg(ogg_file_path, wav_path)
        
        if not success:
            # Если ffmpeg не работает, пробуем pydub
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_ogg(ogg_file_path)
                audio.export(wav_path, format="wav")
            except Exception as e:
                raise Exception(f"Не удалось конвертировать аудио. Установите ffmpeg: {str(e)}")
        
        # Распознаем речь
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            
            # Пробуем распознать с указанным языком
            try:
                text = recognizer.recognize_google(audio_data, language=language)
                return text
            except sr.UnknownValueError:
                # Если не удалось распознать с первым языком, пробуем другой
                alternate_lang = "en-US" if language == "ru-RU" else "ru-RU"
                try:
                    text = recognizer.recognize_google(audio_data, language=alternate_lang)
                    return text
                except sr.UnknownValueError:
                    raise Exception("Не удалось распознать речь. Попробуйте говорить четче.")
            except sr.RequestError:
                raise Exception("Ошибка сервиса распознавания речи. Попробуйте позже.")
    
    finally:
        # Удаляем временный WAV файл
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)


def detect_language_from_text(text: str) -> str:
    """
    Определяет язык текста (русский или английский)
    
    Args:
        text: Текст для определения языка
    
    Returns:
        "ru-RU" или "en-US"
    """
    # Проверяем наличие кириллицы
    has_cyrillic = any('а' <= c.lower() <= 'я' or c.lower() in 'ёщ' for c in text)
    has_latin = any('a' <= c.lower() <= 'z' for c in text)
    
    if has_cyrillic and not has_latin:
        return "ru-RU"
    elif has_latin and not has_cyrillic:
        return "en-US"
    else:
        # Если смешанный текст, считаем русским по умолчанию
        return "ru-RU"
