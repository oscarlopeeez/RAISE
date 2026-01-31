from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    #birth_date = models.DateField()
    bank_name = models.ForeignKey("irrbb_app.Banco", on_delete=models.SET_NULL, null=True, blank=True)