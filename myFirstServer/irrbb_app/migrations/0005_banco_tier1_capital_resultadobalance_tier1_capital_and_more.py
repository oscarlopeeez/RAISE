from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('irrbb_app', '0004_delete_curva')]
    operations = [migrations.AddField(model_name='banco', name='tier1_capital', field=models.FloatField(default=0, help_text='Capital de nivel 1 (Tier 1) en euros, base para el Supervisory Outlier Test')), migrations.AddField(model_name='resultadobalance', name='tier1_capital', field=models.FloatField(default=0, help_text='Tier 1 capital usado para el SOT en el momento del cálculo')), migrations.AddField(model_name='resultadobalance', name='valuation_date', field=models.DateField(blank=True, help_text='Fecha de valoración del cálculo (as of)', null=True))]