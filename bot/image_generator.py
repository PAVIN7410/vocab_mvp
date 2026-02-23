# image_generator.py

import tempfile
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()


class ImageGenerationError(Exception):
    pass


def generate_image_for_word(prompt: str, width: int = 512, height: int = 512) -> str:
    """
    Генерирует картинку для слова/фразы через Pollinations.ai и возвращает путь к временному файлу.
    Файл нужно удалить после использования.
    
    Args:
        prompt: текст для генерации (слово или фраза)
        width: ширина изображения (игнорируется Pollinations, оставлено для совместимости)
        height: высота изображения (игнорируется Pollinations, оставлено для совместимости)
    
    Returns:
        str: путь к временному PNG файлу
    """
    print(f"Generating image via Pollinations.ai: {prompt}")
    
    # Кодируем промпт для URL
    encoded_prompt = quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}"
    
    try:
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            raise ImageGenerationError(f"Pollinations API error: {response.status_code}")
        
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(response.content)
            print(f"Image saved to {tf.name}")
            return tf.name
            
    except requests.RequestException as e:
        raise ImageGenerationError(f"Network error: {str(e)}")





    # пример кода
# from PIL import Image
#
# # Открыть изображение
# img = Image.open("cat.jpg")
#
# # Уменьшить
# img.thumbnail((300, 300))
#
# # Сохранить
# img.save("cat_thumb.jpg")