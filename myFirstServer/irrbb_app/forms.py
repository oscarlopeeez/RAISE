from django import forms

from users.models import CustomUser


class UploadContractsForm(forms.Form):
    id_empleado = forms.CharField(
        label="ID del empleado que sube el balance",
        max_length=150,
    )
    excel_file = forms.FileField(label="Excel de contratos (.xlsx)")