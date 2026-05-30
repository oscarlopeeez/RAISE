import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('irrbb_app', '0006_marketcurve_contrato_uniq_banco_numero_contrato_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.AddField(model_name='resultadobalance', name='approved_at', field=models.DateTimeField(blank=True, null=True)), migrations.AddField(model_name='resultadobalance', name='approved_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='aprobaciones', to=settings.AUTH_USER_MODEL))]