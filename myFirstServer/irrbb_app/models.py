from django.db import models

"""
Avoid importing CustomUser directly to prevent potential import cycles.
Use string-based FK reference instead: 'users.CustomUser'.
"""


class Banco(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


class Contrato(models.Model):
    ACTIVO = "ACTIVO"
    PASIVO = "PASIVO"
    FIJO = "FIJO"
    VARIABLE = "VARIABLE"
    FRANCESA = "FRANCESA"
    ALEMANA = "ALEMANA"
    BULLET = "BULLET"

    banco = models.ForeignKey(Banco, on_delete=models.CASCADE, related_name="contratos")
    numero_contrato = models.CharField(max_length=50)
    producto = models.CharField(max_length=100)
    activo_pasivo = models.CharField(max_length=10)
    nominal = models.FloatField()
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()
    tipo_interes = models.CharField(max_length=10)
    tipo_amortizacion = models.CharField(max_length=10)
    cupon_spread = models.FloatField()
    curva_asociada = models.CharField(max_length=100)
    frecuencia_cupon = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)


class ResultadoBalance(models.Model):
    banco = models.ForeignKey(Banco, on_delete=models.CASCADE, related_name="resultados")
    uploaded_by = models.ForeignKey('users.CustomUser', related_name = "mis_resultados", on_delete=models.SET_NULL, null=True)
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    eve_base = models.FloatField(default=0)
    eve_parallel_up = models.FloatField(default=0)
    eve_parallel_down = models.FloatField(default=0)
    eve_steepener = models.FloatField(default=0)
    eve_flattener = models.FloatField(default=0)
    eve_short_up = models.FloatField(default=0)
    eve_short_down = models.FloatField(default=0)

    nii_base = models.FloatField(default=0)
    nii_parallel_up = models.FloatField(default=0)
    nii_parallel_down = models.FloatField(default=0)

    metadata = models.JSONField(default=dict, blank=True)
