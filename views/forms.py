from django import forms
from .models import Word

class WordForm(forms.ModelForm):
    class Meta:
        model = Word
        fields = ['text']  # Field 'user' will be set in the view