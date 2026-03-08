# bot/image_generator.py
import tempfile


def fetch_image_for_word(word_text, translation):
    """Генерирует картинку через Pollinations и возвращает Django File"""

    try:
        import requests

        # Формируем запрос к Pollinations
        prompt = f"{word_text} ({translation})"
        url = f"https://image.pollinations.ai/prompt/{prompt}?nologo=true"

        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"⚠️ Pollinations ошибка: {response.status_code}")
            return None

        # Создаём временный файл ПО-НОВОМУ (совместимо с Python 3.14)
        img_temp = tempfile.NamedTemporaryFile(
            suffix='.jpg',  # ✅ Вместо delete=True
            mode='wb',
            delete=False  # ✅ Явно отключаем автоудаление
        )

        img_temp.write(response.content)
        img_temp.close()

        # Возвращаем как Django File
        from django.core.files.uploadedfile import SimpleUploadedFile
        file = SimpleUploadedFile(
            name=f"{word_text}.jpg",
            content=response.content,
            content_type="image/jpeg"
        )

        # Удаляем временный файл сразу после загрузки
        import os
        os.remove(img_temp.name)

        return file

    except Exception as e:
        print(f"Ошибка генерации картинки: {e}")
        return None