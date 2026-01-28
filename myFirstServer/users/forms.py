from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    birth_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "birth_date", "bank_name")
        