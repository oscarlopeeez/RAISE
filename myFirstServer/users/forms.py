from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser
from irrbb_app.models import Banco


class CustomUserCreationForm(UserCreationForm):
    bank_name = forms.ModelChoiceField(queryset=Banco.objects.all(), label="Banco", required=True)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "bank_name", "password1", "password2")