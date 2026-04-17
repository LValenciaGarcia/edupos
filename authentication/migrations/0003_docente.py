from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_padre_saldo_and_panel_completo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='perfil',
            name='rol',
            field=models.CharField(
                choices=[
                    ('admin',      'Administrador'),
                    ('padre',      'Padre de Familia'),
                    ('estudiante', 'Estudiante'),
                    ('docente',    'Docente'),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='Docente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('documento',    models.CharField(blank=True, max_length=20, verbose_name='N° Documento (CC)')),
                ('materia',      models.CharField(blank=True, max_length=100, verbose_name='Materia / Área')),
                ('saldo',        models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('limite_fiado', models.DecimalField(
                    decimal_places=2, default=50000, max_digits=10,
                    verbose_name='Límite de crédito (fiado)',
                    help_text='Monto máximo que puede pedir sin saldo suficiente',
                )),
                ('deuda_fiado',  models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Deuda de fiado')),
                ('perfil', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='docente',
                    to='authentication.perfil',
                )),
            ],
            options={
                'verbose_name': 'Docente',
                'verbose_name_plural': 'Docentes',
            },
        ),
    ]
