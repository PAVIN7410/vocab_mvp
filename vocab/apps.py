# vocab/apps.py

from django.apps import AppConfig

class VocabConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vocab'

    def ready(self):
        # Это заставит Django загрузить models.py и зарегистрировать сигналы
        pass
