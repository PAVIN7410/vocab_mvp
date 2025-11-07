from django.shortcuts import render, redirect
from words.models import Word
from .forms import WordForm
# Assuming google-cloud-translate is used instead
from google.cloud import translate_v2 as translate
from vocab.models import TelegramUser

translate_client = translate.Client()


def word_list(request):
    words = Word.objects.all()
    if not words.exists():
        return render(request, 'word_list.html', {'message': 'No words available. Please add words first.'})
    return render(request, 'word_list.html', {'words': words})


def word_create(request):
    if request.method == "POST":
        form = WordForm(request.POST)
        if form.is_valid():
            word = form.save(commit=False)
            word.user = TelegramUser.objects.first()
            # Assuming a single user for now, update logic as needed
            translated_text = translate_client.translate(word.text, source_language='en', target_language='ru')['translatedText']
            word.translation = translated_text
            word.save()
            return redirect('word_list')
    else:
        form = WordForm()
    return render(request, 'word_form.html', {'form': form})

