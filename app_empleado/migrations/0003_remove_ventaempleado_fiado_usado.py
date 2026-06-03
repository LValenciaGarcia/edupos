# Eliminación del campo fiado_usado al retirar el sistema de fiado.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app_empleado', '0002_ventaempleado_anulada_ventaempleado_fiado_usado_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ventaempleado',
            name='fiado_usado',
        ),
    ]
