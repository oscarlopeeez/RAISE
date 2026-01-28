from django.contrib import admin

from .models import Banco, Curva, Contrato, ResultadoBalance


@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "created_at")
    search_fields = ("nombre",)


@admin.register(Curva)
class CurvaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "fecha")
    list_filter = ("fecha",)
    search_fields = ("nombre",)


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = (
        "numero_contrato",
        "banco",
        "producto",
        "activo_pasivo",
        "nominal",
        "tipo_interes",
        "tipo_amortizacion",
        "curva_asociada",
        "frecuencia_cupon",
        "created_at",
    )
    list_filter = ("activo_pasivo", "tipo_interes", "tipo_amortizacion", "banco")
    search_fields = ("numero_contrato", "producto", "curva_asociada")


@admin.register(ResultadoBalance)
class ResultadoBalanceAdmin(admin.ModelAdmin):
    list_display = (
        "banco",
        "fecha_calculo",
        "eve_base",
        "eve_parallel_up",
        "eve_parallel_down",
        "eve_steepener",
        "eve_flattener",
        "eve_short_up",
        "eve_short_down",
        "nii_base",
        "nii_parallel_up",
        "nii_parallel_down",
    )
    list_filter = ("banco", "fecha_calculo")
