# Eliminación completa del sistema de fiado en app_docente.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_docente', '0005_recargadocente_mp_payment_id_and_more'),
        ('authentication', '0009_remove_docente_fiado'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MovimientoFiado',
        ),
        migrations.RemoveField(
            model_name='pedidodocente',
            name='tipo_pago',
        ),
        migrations.RemoveField(
            model_name='pedidoprogramadodocente',
            name='tipo_pago',
        ),
        migrations.AlterField(
            model_name='notificaciondocente',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('pedido_listo', 'Pedido Listo'),
                    ('pedido_grupal', 'Pedido Grupal'),
                    ('info', 'Información'),
                ],
                default='info',
                max_length=20,
            ),
        ),
    ]
