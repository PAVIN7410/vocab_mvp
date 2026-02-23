# vocab/deep_translate.py

from deep_translator import GoogleTranslator

text = "Hello, how are you?"
translated = GoogleTranslator(source='en', target='ru').translate(text)
print(translated)  # Привет, как дела?