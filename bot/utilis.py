# bot/utilis.py
import os
import requests

# Убедимся, что переменная окружения есть
DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://127.0.0.1:8000/api/")

def register_user(telegram_id, username):
    try:
        response = requests.post(
            f'{DJANGO_API_URL}register/',
            json={'telegram_id': telegram_id, 'username': username},
            timeout=5
        )
        return response
    except requests.exceptions.RequestException as e:
        print(f"Ошибка связи с Django API: {e}")
        return None



