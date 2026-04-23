"""
Migration 0010: Ingredient lot system + production model.

Changes:
  - Ingrediente: add proveedor FK, remove stock_unidades / precio_compra / fecha_vencimiento
  - New: LoteIngrediente (per-batch stock with expiry date and FIFO logic)
  - New: ProduccionElaborado (registers production of elaborated products)
  - Data migration: converts existing stock_unidades + precio_compra into initial lots
"""
import datetime
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def crear_lotes_desde_stock(apps, schema_editor):
    Ingrediente = apps.get_model('app_admin', 'Ingrediente')
    LoteIngrediente = apps.get_model('app_admin', 'LoteIngrediente')
    Proveedor = apps.get_model('app_admin', 'Proveedor')

    primer_proveedor = Proveedor.objects.first()
    vence_default = datetime.date.today() + datetime.timedelta(days=365)

    for ing in Ingrediente.objects.all():
        stock_u = float(ing.stock_unidades or 0)
        precio_c = float(ing.precio_compra or 0)
        contenido = float(ing.contenido_por_unidad or 1)
        fecha_venc = ing.fecha_vencimiento or vence_default

        if primer_proveedor:
            ing.proveedor = primer_proveedor
            ing.save(update_fields=['proveedor'])

        cantidad_base = round(stock_u * contenido, 3)
        if cantidad_base > 0 and primer_proveedor:
            LoteIngrediente.objects.create(
                ingrediente=ing,
                proveedor=primer_proveedor,
                unidades_compra=stock_u,
                precio_compra=precio_c,
                cantidad_base=cantidad_base,
                cantidad_base_inicial=cantidad_base,
                fecha_vencimiento=fecha_venc,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('app_admin', '0009_ingrediente_v2_inventario'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Add proveedor FK to Ingrediente (null=True for backward compat during migration)
        migrations.AddField(
            model_name='ingrediente',
            name='proveedor',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='ingredientes',
                to='app_admin.proveedor',
                verbose_name='Proveedor principal',
            ),
        ),

        # 2. Create LoteIngrediente
        migrations.CreateModel(
            name='LoteIngrediente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unidades_compra', models.DecimalField(decimal_places=2, max_digits=10, help_text='Cantidad de unidades de compra recibidas')),
                ('precio_compra', models.DecimalField(decimal_places=2, max_digits=10, help_text='Precio por unidad de compra')),
                ('cantidad_base', models.DecimalField(decimal_places=3, max_digits=10, help_text='Stock actual en unidades base')),
                ('cantidad_base_inicial', models.DecimalField(decimal_places=3, max_digits=10, help_text='Stock inicial en unidades base')),
                ('fecha_vencimiento', models.DateField()),
                ('fecha_ingreso', models.DateField(auto_now_add=True)),
                ('nota', models.CharField(blank=True, max_length=200)),
                ('compra', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='lotes_ingrediente',
                    to='app_admin.compraproveedor',
                )),
                ('ingrediente', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='lotes',
                    to='app_admin.ingrediente',
                )),
                ('proveedor', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='lotes_ingrediente',
                    to='app_admin.proveedor',
                )),
            ],
            options={
                'verbose_name': 'Lote de Ingrediente',
                'verbose_name_plural': 'Lotes de Ingredientes',
                'ordering': ['fecha_vencimiento'],
            },
        ),

        # 3. Create ProduccionElaborado
        migrations.CreateModel(
            name='ProduccionElaborado',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad_producida', models.PositiveIntegerField()),
                ('costo_total', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('nota', models.TextField(blank=True)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('producto', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='producciones',
                    to='app_admin.producto',
                )),
                ('responsable', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='producciones',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Producción',
                'verbose_name_plural': 'Producciones',
                'ordering': ['-fecha'],
            },
        ),

        # 4. Data migration: create initial lots from existing stock data
        migrations.RunPython(crear_lotes_desde_stock, migrations.RunPython.noop),

        # 5. Remove obsolete fields from Ingrediente
        migrations.RemoveField(model_name='ingrediente', name='stock_unidades'),
        migrations.RemoveField(model_name='ingrediente', name='precio_compra'),
        migrations.RemoveField(model_name='ingrediente', name='fecha_vencimiento'),
    ]
