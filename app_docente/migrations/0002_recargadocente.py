from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app_docente', '0001_initial'),
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecargaDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('monto', models.DecimalField(decimal_places=2, max_digits=10)),
                ('comprobante', models.ImageField(blank=True, null=True, upload_to='recargas/docentes/')),
                ('nota', models.CharField(blank=True, max_length=300)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('rechazada', 'Rechazada')], default='pendiente', max_length=15)),
                ('nota_admin', models.CharField(blank=True, max_length=300, verbose_name='Nota del administrador')),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('fecha_resolucion', models.DateTimeField(blank=True, null=True)),
                ('docente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recargas', to='authentication.docente')),
            ],
            options={
                'verbose_name': 'Recarga Docente',
                'verbose_name_plural': 'Recargas Docente',
                'ordering': ['-fecha'],
            },
        ),
    ]
