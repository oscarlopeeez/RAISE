from django import forms

from users.models import CustomUser


class UploadContractsForm(forms.Form):
    excel_file = forms.FileField(label="Excel de contratos (.xlsx)")