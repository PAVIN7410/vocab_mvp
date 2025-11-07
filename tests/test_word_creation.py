from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from vocab.models import TelegramUser, Word

class WordCreationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = TelegramUser.objects.create(telegram_id=12345, username='TestUser')
        self.word_data = {
            'text': 'test',
            'translation': 'тест'
        }

    def test_word_creation(self):
        response = self.client.post(reverse('word-create'), self.word_data)
        self.assertEqual(response.status_code, 302)  # should redirect after creation

        word = Word.objects.first()
        self.assertIsNotNone(word)
        self.assertEqual(word.text, 'test')
        self.assertEqual(word.translation, 'тест')
        self.assertEqual(word.user, self.user)
