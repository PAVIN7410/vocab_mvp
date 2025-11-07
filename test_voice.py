#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки функции озвучивания
"""

import os
import sys

# Добавляем корневую директорию проекта в PYTHONPATH
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bot.voice import synthesize_text_to_mp3

def test_voice_english():
    """Тест озвучивания английского слова"""
    print("🔊 Тестируем озвучивание английского слова 'request'...")
    try:
        audio_path = synthesize_text_to_mp3("request", lang="en")
        print(f"✅ Аудио файл создан: {audio_path}")
        
        # Проверяем, что файл существует
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            print(f"📁 Размер файла: {file_size} байт")
            
            # Удаляем файл после проверки
            os.remove(audio_path)
            print("🗑️ Тестовый файл удален")
            return True
        else:
            print("❌ Файл не был создан!")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_voice_russian():
    """Тест озвучивания русского слова"""
    print("\n🔊 Тестируем озвучивание русского слова 'запрос'...")
    try:
        audio_path = synthesize_text_to_mp3("запрос", lang="ru")
        print(f"✅ Аудио файл создан: {audio_path}")
        
        # Проверяем, что файл существует
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            print(f"📁 Размер файла: {file_size} байт")
            
            # Удаляем файл после проверки
            os.remove(audio_path)
            print("🗑️ Тестовый файл удален")
            return True
        else:
            print("❌ Файл не был создан!")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("=" * 50)
    print("🎤 ТЕСТИРОВАНИЕ ОЗВУЧИВАНИЯ")
    print("=" * 50)
    
    test1 = test_voice_english()
    test2 = test_voice_russian()
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ")
    print("=" * 50)
    print(f"Английский: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Русский: {'✅ PASSED' if test2 else '❌ FAILED'}")
    
    if test1 and test2:
        print("\n✨ Все тесты пройдены успешно!")
        return 0
    else:
        print("\n⚠️ Некоторые тесты не прошли!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
