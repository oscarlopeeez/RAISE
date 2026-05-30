from django.db import models
"\nAvoid importing CustomUser directly to prevent potential import cycles.\nUse string-based FK reference instead: 'users.CustomUser'.\n"

class Banco(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    tier1_capital = models.FloatField(default=0, help_text='Capital de nivel 1 (Tier 1) en euros, base para el Supervisory Outlier Test')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

class Contrato(models.Model):
    ACTIVO = 'ACTIVO'
    PASIVO = 'PASIVO'
    FIJO = 'FIJO'
    VARIABLE = 'VARIABLE'
    FRANCESA = 'FRANCESA'
    ALEMANA = 'ALEMANA'
    BULLET = 'BULLET'
    banco = models.ForeignKey(Banco, on_delete=models.CASCADE, related_name='contratos')
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

    class Meta:
        constraints = [models.UniqueConstraint(fields=['banco', 'numero_contrato'], name='uniq_banco_numero_contrato')]

class MarketCurve(models.Model):
    SOURCE_ECB = 'ECB'
    source = models.CharField(max_length=20, default=SOURCE_ECB)
    fetched_at = models.DateTimeField(auto_now_add=True)
    reference_date = models.DateField(help_text='Fecha de los datos de la curva')
    currency = models.CharField(max_length=3, default='EUR')
    tenors = models.JSONField(default=list)

    class Meta:
        ordering = ['-reference_date', '-fetched_at']
        indexes = [models.Index(fields=['source', '-reference_date'])]

class ResultadoBalance(models.Model):
    banco = models.ForeignKey(Banco, on_delete=models.CASCADE, related_name='resultados')
    uploaded_by = models.ForeignKey('users.CustomUser', related_name='mis_resultados', on_delete=models.SET_NULL, null=True)
    fecha_calculo = models.DateTimeField(auto_now_add=True)
    valuation_date = models.DateField(null=True, blank=True, help_text='Fecha de valoración del cálculo (as of)')
    tier1_capital = models.FloatField(default=0, help_text='Tier 1 capital usado para el SOT en el momento del cálculo')
    approved_by = models.ForeignKey('users.CustomUser', related_name='aprobaciones', null=True, blank=True, on_delete=models.SET_NULL)
    approved_at = models.DateTimeField(null=True, blank=True)
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