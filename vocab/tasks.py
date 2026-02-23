#vocab/tasks.py:
import requests
from django.utils import timezone

from celery import shared_task
from .models import Repetition


@shared_task
def send_review_notifications():
    now = timezone.now()
    reps = Repetition.objects.filter(next_review__lte=now)
    for rep in reps:
        tg_id = rep.card.owner.telegram_id
        requests.post('http://localhost:8000/bot/send_notification/', json={'telegram_id': tg_id, 'card_id': rep.card.id})
