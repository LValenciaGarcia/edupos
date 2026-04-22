from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_docente', '0003_alter_recargadocente_comprobante_movimientofiado'),
    ]

    operations = [
        migrations.AddField(
            model_name='reseñaproducto',
            name='sentimiento',
            field=models.CharField(
                choices=[('positivo', 'Positivo'), ('neutro', 'Neutro'), ('negativo', 'Negativo')],
                default='neutro',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='reseñaproducto',
            name='visible',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='reseñaproducto',
            name='razon_rechazo',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
