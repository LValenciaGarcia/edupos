from django.db import migrations, models
import django.db.models.deletion
import authentication.validators


class Migration(migrations.Migration):

    dependencies = [
        ('app_padre', '0005_detalleprogramado_precio_unitario_and_more'),
        ('authentication', '0006_sede_alter_perfil_rol_historicalempleado_empleado'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecargaPadre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=10)),
                ('comprobante', models.ImageField(blank=True, null=True, upload_to='recargas/padres/', validators=[authentication.validators.validate_image])),
                ('nota', models.CharField(blank=True, max_length=300)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('rechazada', 'Rechazada')], default='pendiente', max_length=15)),
                ('nota_admin', models.CharField(blank=True, max_length=300, verbose_name='Nota del administrador')),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('fecha_resolucion', models.DateTimeField(blank=True, null=True)),
                ('padre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recargas_propias', to='authentication.padre')),
            ],
            options={
                'verbose_name': 'Recarga de Padre',
                'verbose_name_plural': 'Recargas de Padre',
                'ordering': ['-fecha'],
            },
        ),
    ]
