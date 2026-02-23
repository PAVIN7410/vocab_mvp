# vocab/db_utils.py
from typing import Optional

try:
    from vocab.models import Card  # твоя модель называется Card
except Exception:
    Card = None

def save_card(word_en: str, word_ru: str, translation: str, audio_path: str, user_id: int) -> Optional[object]:
    """
    Сохранение карточки в Django-базе данных.
    - word_en: английское слово
    - word_ru: русское слово/оригинал
    - translation: перевод
    - audio_path: путь к аудиофайлу
    - user_id: ID Telegram-пользователя (ForeignKey к пользователю)

    Возвращает созданную запись или None.
    """
    if Card is None:
        return None
    try:
        card = Card(
            user_id=user_id,
            word_en=word_en,
            word_ru=word_ru,
            translation=translation,
            audio_path=audio_path
            # DIFFICULTY можно установить по умолчанию, если есть поле
            # difficulty= some_default
        )
        card.save()
        return card
    except Exception:
        return None