from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_docente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='docente',
            name='limite_fiado',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=10,
                verbose_name='Límite de crédito (fiado)',
                help_text='Monto máximo que puede pedir sin saldo suficiente',
            ),
        ),
    ]
