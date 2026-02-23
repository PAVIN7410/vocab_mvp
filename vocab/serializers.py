#vocab/serializers.py:

from rest_framework import serializers

from .models import TelegramUser, Card, Repetition


class TelegramUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramUser
        fields = ['id', 'telegram_id', 'username']

class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = '__all__'

class RepetitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repetition
        fields = '__all__'
