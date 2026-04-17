from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0003_docente'),
        ('app_admin', '0001_initial'),
    ]

    operations = [
        # ── PedidoGrupal ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='PedidoGrupal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo',  models.CharField(default='Pedido grupal sala de profes', max_length=120)),
                ('estado',  models.CharField(
                    choices=[('abierto','Abierto (aceptando participantes)'),('cerrado','Cerrado / En preparación'),('entregado','Entregado'),('cancelado','Cancelado')],
                    default='abierto', max_length=12,
                )),
                ('fecha',   models.DateTimeField(default=django.utils.timezone.now)),
                ('nota',    models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organizador', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pedidos_grupales_organizados',
                    to='authentication.docente',
                )),
            ],
            options={'verbose_name': 'Pedido Grupal', 'verbose_name_plural': 'Pedidos Grupales', 'ordering': ['-fecha']},
        ),

        # ── PedidoDocente ─────────────────────────────────────────────────
        migrations.CreateModel(
            name='PedidoDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ticket',      models.CharField(editable=False, max_length=20, unique=True)),
                ('estado',      models.CharField(
                    choices=[('pendiente','Pendiente'),('preparando','En preparación'),('listo','Listo para recoger'),('entregado','Entregado'),('cancelado','Cancelado')],
                    default='pendiente', max_length=15,
                )),
                ('tipo_pago',   models.CharField(choices=[('saldo','Saldo'),('fiado','Fiado (crédito)')], default='saldo', max_length=10)),
                ('total',       models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('nota',        models.TextField(blank=True)),
                ('fecha_pedido', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('updated_at',  models.DateTimeField(auto_now=True)),
                ('docente', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='pedidos',
                    to='authentication.docente',
                )),
                ('pedido_grupal', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='pedidos_miembros',
                    to='app_docente.pedidogrupal',
                )),
            ],
            options={'verbose_name': 'Pedido Docente', 'verbose_name_plural': 'Pedidos Docente', 'ordering': ['-fecha_pedido']},
        ),

        # ── DetallePedidoDocente ──────────────────────────────────────────
        migrations.CreateModel(
            name='DetallePedidoDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad',        models.PositiveIntegerField(default=1)),
                ('precio_unitario', models.DecimalField(decimal_places=2, max_digits=10)),
                ('pedido',   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='app_docente.pedidodocente')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='detalles_docente', to='app_admin.producto')),
            ],
            options={'verbose_name': 'Detalle Pedido Docente', 'verbose_name_plural': 'Detalles Pedido Docente'},
        ),

        # ── PedidoProgramadoDocente ───────────────────────────────────────
        migrations.CreateModel(
            name='PedidoProgramadoDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_entrega', models.DateField()),
                ('hora_entrega',  models.TimeField(blank=True, null=True)),
                ('nota',          models.TextField(blank=True)),
                ('tipo_pago',     models.CharField(choices=[('saldo','Saldo'),('fiado','Fiado (crédito)')], default='saldo', max_length=10)),
                ('estado',        models.CharField(choices=[('activo','Activo'),('procesado','Procesado'),('cancelado','Cancelado')], default='activo', max_length=12)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
                ('docente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pedidos_programados', to='authentication.docente')),
                ('pedido',  models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='programados', to='app_docente.pedidodocente')),
            ],
            options={'verbose_name': 'Pedido Programado Docente', 'verbose_name_plural': 'Pedidos Programados Docente', 'ordering': ['fecha_entrega']},
        ),

        # ── DetalleProgramadoDocente ──────────────────────────────────────
        migrations.CreateModel(
            name='DetalleProgramadoDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad',    models.PositiveIntegerField(default=1)),
                ('pedido_prog', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='app_docente.pedidoprogramadodocente')),
                ('producto',    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='app_admin.producto')),
            ],
            options={'verbose_name': 'Detalle Pedido Programado Docente', 'verbose_name_plural': 'Detalles Pedidos Programados Docente'},
        ),

        # ── FavoritoDocente ───────────────────────────────────────────────
        migrations.CreateModel(
            name='FavoritoDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('docente',  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favoritos', to='authentication.docente')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favoritos_docente', to='app_admin.producto')),
            ],
            options={'verbose_name': 'Favorito Docente', 'verbose_name_plural': 'Favoritos Docente', 'unique_together': {('docente', 'producto')}, 'ordering': ['-created_at']},
        ),

        # ── ReseñaProducto ────────────────────────────────────────────────
        migrations.CreateModel(
            name='ReseñaProducto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('calificacion', models.PositiveSmallIntegerField(choices=[(1,'1 estrella'),(2,'2 estrellas'),(3,'3 estrellas'),(4,'4 estrellas'),(5,'5 estrellas')], default=5)),
                ('comentario',   models.TextField(blank=True, max_length=500)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('updated_at',   models.DateTimeField(auto_now=True)),
                ('docente',  models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reseñas', to='authentication.docente')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reseñas_docente', to='app_admin.producto')),
            ],
            options={'verbose_name': 'Reseña de Producto', 'verbose_name_plural': 'Reseñas de Productos', 'unique_together': {('docente', 'producto')}, 'ordering': ['-created_at']},
        ),

        # ── NotificacionDocente ───────────────────────────────────────────
        migrations.CreateModel(
            name='NotificacionDocente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo',       models.CharField(choices=[('pedido_listo','Pedido Listo'),('fiado_cerca','Límite Fiado Cerca'),('pedido_grupal','Pedido Grupal'),('info','Información')], default='info', max_length=20)),
                ('titulo',     models.CharField(max_length=150)),
                ('mensaje',    models.TextField()),
                ('leida',      models.BooleanField(default=False)),
                ('url_accion', models.CharField(blank=True, max_length=200)),
                ('fecha',      models.DateTimeField(auto_now_add=True)),
                ('docente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones', to='authentication.docente')),
            ],
            options={'verbose_name': 'Notificación Docente', 'verbose_name_plural': 'Notificaciones Docente', 'ordering': ['-fecha']},
        ),
    ]
