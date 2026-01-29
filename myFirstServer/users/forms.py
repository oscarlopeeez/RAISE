from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

# BANK_CHOICES = [
#     ('', '--- Selecciona un banco ---'),
#     ('Santander', 'Santander'),
#     ('BBVA', 'BBVA'),
#     ('Bankinter', 'Bankinter'),
#     ('CaixaBank', 'CaixaBank'),
#     ('Sabadell', 'Sabadell'),
#     ('Kutxabank', 'Kutxabank'),
# ]

class CustomUserCreationForm(UserCreationForm):
    birth_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    bank_name = forms.CharField(label="Banco", required=True)

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "email", "birth_date", "bank_name")
