# Eliminación del sistema de fiado del modelo Docente.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_estudiante_puede_recargar_autonomo_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='docente',
            name='limite_fiado',
        ),
        migrations.RemoveField(
            model_name='docente',
            name='deuda_fiado',
        ),
        migrations.RemoveField(
            model_name='historicaldocente',
            name='limite_fiado',
        ),
        migrations.RemoveField(
            model_name='historicaldocente',
            name='deuda_fiado',
        ),
    ]
