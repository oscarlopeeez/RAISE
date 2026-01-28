from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Additional Info", {"fields": ("birth_date", "bank_name")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {"fields": ("birth_date", "bank_name")}),
    )
