from django.db import migrations, models


def migrar_campos_ingrediente(apps, schema_editor):
    """
    Copia los datos del modelo antiguo al nuevo esquema:
    - stock        → stock_unidades   (1:1 con contenido_por_unidad=1)
    - unidad       → unidad_base
    - precio_unitario → precio_compra (costo_unitario_real = precio_compra/1 = mismo valor)
    La equivalencia matemática se preserva: stock_real = stock_unidades * 1 = stock_anterior
    """
    Ingrediente = apps.get_model('app_admin', 'Ingrediente')
    for ing in Ingrediente.objects.all():
        ing.stock_unidades       = ing.stock
        ing.unidad_compra        = 'und'
        ing.contenido_por_unidad = 1
        ing.unidad_base          = ing.unidad
        ing.precio_compra        = ing.precio_unitario
        ing.save()


class Migration(migrations.Migration):

    dependencies = [
        ('app_admin', '0008_update_alergeno_iconos'),
    ]

    operations = [
        # ── 1. Agregar nuevos campos (con defaults para no romper filas existentes) ──
        migrations.AddField(
            model_name='ingrediente',
            name='stock_unidades',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                help_text='Cantidad de unidades de compra disponibles (ej: 10 bandejas)',
            ),
        ),
        migrations.AddField(
            model_name='ingrediente',
            name='unidad_compra',
            field=models.CharField(
                default='und', max_length=50,
                help_text='Nombre de la unidad de compra (ej: bandeja, paquete, bolsa)',
            ),
        ),
        migrations.AddField(
            model_name='ingrediente',
            name='contenido_por_unidad',
            field=models.DecimalField(
                decimal_places=4, default=1, max_digits=10,
                help_text='Cuántas unidades base contiene cada unidad de compra (ej: 12 huevos por bandeja)',
            ),
        ),
        migrations.AddField(
            model_name='ingrediente',
            name='unidad_base',
            field=models.CharField(
                choices=[
                    ('g',        'Gramos (g)'),
                    ('kg',       'Kilogramos (kg)'),
                    ('ml',       'Mililitros (ml)'),
                    ('l',        'Litros (l)'),
                    ('und',      'Unidades'),
                    ('porciones','Porciones'),
                ],
                default='und', max_length=10,
                help_text='Unidad en la que se mide para recetas (ej: und, g, ml)',
            ),
        ),
        migrations.AddField(
            model_name='ingrediente',
            name='precio_compra',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=10,
                help_text='Precio pagado por cada unidad de compra (ej: $8.000 por bandeja)',
            ),
        ),
        # ── 2. Migrar datos del esquema antiguo al nuevo ──────────────────────
        migrations.RunPython(migrar_campos_ingrediente, migrations.RunPython.noop),
        # ── 3. Eliminar campos obsoletos ──────────────────────────────────────
        migrations.RemoveField(model_name='ingrediente', name='unidad'),
        migrations.RemoveField(model_name='ingrediente', name='precio_unitario'),
        migrations.RemoveField(model_name='ingrediente', name='stock'),
        migrations.RemoveField(model_name='ingrediente', name='stock_maximo'),
        migrations.RemoveField(model_name='ingrediente', name='porcentaje_merma'),
        migrations.RemoveField(model_name='ingrediente', name='proveedor'),
    ]
