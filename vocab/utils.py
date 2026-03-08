#vocab/utils.py:
from .models import TelegramUser


def get_tg_user(request):
    """Получает TelegramUser из сессии."""
    tg_id = request.session.get('telegram_id')

    if not tg_id:
        # Пробуем найти по Django User
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                tg_user = TelegramUser.objects.get(user=request.user)
                request.session['telegram_id'] = tg_user.telegram_id
                return tg_user
            except TelegramUser.DoesNotExist:
                pass
        return None

    try:
        return TelegramUser.objects.get(telegram_id=str(tg_id))
    except TelegramUser.DoesNotExist:
        return None