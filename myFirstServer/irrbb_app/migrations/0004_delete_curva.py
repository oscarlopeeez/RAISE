from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('irrbb_app', '0003_alter_resultadobalance_uploaded_by')]
    operations = [migrations.DeleteModel(name='Curva')]