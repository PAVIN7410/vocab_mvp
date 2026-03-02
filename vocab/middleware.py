# vocab/middleware.py
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin

from .models import TelegramUser


class TelegramAuthMiddleware(MiddlewareMixin):
    """
    Middleware для автоматической аутентификации пользователей Telegram.
    Если в сессии есть telegram_id, создаём/получаем Django User и логиним его.
    """
    
    def process_request(self, request):
        telegram_id = request.session.get('telegram_id')
        
        # Если telegram_id есть в сессии и пользователь не залогинен
        if telegram_id and not request.user.is_authenticated:
            try:
                # Находим TelegramUser
                tg_user = TelegramUser.objects.get(telegram_id=int(telegram_id))
                
                # Если у него нет привязанного Django User - создаём
                if not tg_user.user:
                    django_user = User.objects.create_user(
                        username=f'tg_{telegram_id}',
                        password=None  # Пароль не нужен, вход только через бота
                    )
                    tg_user.user = django_user
                    tg_user.save()
                
                # Логиним пользователя
                login(request, tg_user.user, backend='django.contrib.auth.backends.ModelBackend')
                
                # Добавляем tg_user к request для удобного доступа
                request.tg_user = tg_user
                
            except TelegramUser.DoesNotExist:
                # Если TelegramUser не найден - просто продолжаем без аутентификации
                request.tg_user = None
        
        # Если пользователь уже залогинен, добавляем tg_user
        elif request.user.is_authenticated:
            try:
                request.tg_user = TelegramUser.objects.get(user=request.user)
            except TelegramUser.DoesNotExist:
                request.tg_user = None
        else:
            request.tg_user = None
