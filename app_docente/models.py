from django.db import models
from django.utils import timezone
from authentication.models import Docente
from authentication.validators import validate_image
from app_admin.models import Producto, Categoria


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDO DOCENTE
# ══════════════════════════════════════════════════════════════════════════════

class PedidoDocente(models.Model):
    ESTADO_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('preparando', 'En preparación'),
        ('listo',      'Listo para recoger'),
        ('entregado',  'Entregado'),
        ('cancelado',  'Cancelado'),
    ]
    PAGO_CHOICES = [
        ('saldo', 'Saldo'),
        ('fiado', 'Fiado (crédito)'),
    ]

    ticket        = models.CharField(max_length=20, unique=True, editable=False)
    docente       = models.ForeignKey(Docente, on_delete=models.PROTECT, related_name='pedidos')
    estado        = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    tipo_pago     = models.CharField(max_length=10, choices=PAGO_CHOICES, default='saldo')
    total         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nota          = models.TextField(blank=True)
    pedido_grupal = models.ForeignKey(
        'PedidoGrupal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pedidos_miembros',
    )
    fecha_pedido  = models.DateTimeField(default=timezone.now)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.ticket:
            año = timezone.now().year
            ultimo = PedidoDocente.objects.filter(ticket__startswith=f'PD-{año}-').order_by('-ticket').first()
            num = (int(ultimo.ticket.split('-')[-1]) + 1) if ultimo else 1
            self.ticket = f'PD-{año}-{num:05d}'
        super().save(*args, **kwargs)

    def recalcular_total(self):
        self.total = sum(float(d.subtotal) for d in self.detalles.all())
        self.save(update_fields=['total'])

    def __str__(self):
        return f'{self.ticket} — {self.docente} [{self.get_estado_display()}]'

    class Meta:
        verbose_name = 'Pedido Docente'
        verbose_name_plural = 'Pedidos Docente'
        ordering = ['-fecha_pedido']


class DetallePedidoDocente(models.Model):
    pedido          = models.ForeignKey(PedidoDocente, on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_docente')
    cantidad        = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return round(float(self.cantidad) * float(self.precio_unitario), 2)

    def save(self, *args, **kwargs):
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.cantidad}× {self.producto.nombre} en {self.pedido.ticket}'

    class Meta:
        verbose_name = 'Detalle Pedido Docente'
        verbose_name_plural = 'Detalles Pedido Docente'


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDO PROGRAMADO DOCENTE
# ══════════════════════════════════════════════════════════════════════════════

class PedidoProgramadoDocente(models.Model):
    ESTADO_CHOICES = [
        ('activo',    'Activo'),
        ('procesado', 'Procesado'),
        ('cancelado', 'Cancelado'),
    ]

    docente       = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='pedidos_programados')
    fecha_entrega = models.DateField()
    hora_entrega  = models.TimeField(null=True, blank=True)
    nota          = models.TextField(blank=True)
    tipo_pago     = models.CharField(max_length=10, choices=PedidoDocente.PAGO_CHOICES, default='saldo')
    estado        = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='activo')
    pedido        = models.ForeignKey(
        PedidoDocente, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='programados',
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    @property
    def total(self):
        return sum(d.subtotal for d in self.detalles.all())

    def __str__(self):
        return f'Programado {self.fecha_entrega} — {self.docente}'

    class Meta:
        verbose_name = 'Pedido Programado Docente'
        verbose_name_plural = 'Pedidos Programados Docente'
        ordering = ['fecha_entrega']


class DetalleProgramadoDocente(models.Model):
    pedido_prog = models.ForeignKey(PedidoProgramadoDocente, on_delete=models.CASCADE, related_name='detalles')
    producto    = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad    = models.PositiveIntegerField(default=1)

    @property
    def subtotal(self):
        return float(self.cantidad) * float(self.producto.precio_venta)

    def __str__(self):
        return f'{self.cantidad}× {self.producto.nombre}'

    class Meta:
        verbose_name = 'Detalle Pedido Programado Docente'
        verbose_name_plural = 'Detalles Pedidos Programados Docente'


# ══════════════════════════════════════════════════════════════════════════════
# FAVORITOS
# ══════════════════════════════════════════════════════════════════════════════

class FavoritoDocente(models.Model):
    docente  = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='favoritos')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='favoritos_docente')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.docente} ♥ {self.producto.nombre}'

    class Meta:
        verbose_name = 'Favorito Docente'
        verbose_name_plural = 'Favoritos Docente'
        unique_together = ['docente', 'producto']
        ordering = ['-created_at']


# ══════════════════════════════════════════════════════════════════════════════
# RESEÑAS DE PRODUCTOS
# ══════════════════════════════════════════════════════════════════════════════

class ReseñaProducto(models.Model):
    docente    = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='reseñas')
    producto   = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='reseñas_docente')
    calificacion = models.PositiveSmallIntegerField(
        choices=[(i, f'{i} estrella{"s" if i > 1 else ""}') for i in range(1, 6)],
        default=5,
    )
    comentario = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Reseña {self.calificacion}★ de {self.docente} → {self.producto.nombre}'

    class Meta:
        verbose_name = 'Reseña de Producto'
        verbose_name_plural = 'Reseñas de Productos'
        unique_together = ['docente', 'producto']
        ordering = ['-created_at']


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDO GRUPAL — "Sala de Profes"
# ══════════════════════════════════════════════════════════════════════════════

class PedidoGrupal(models.Model):
    """Un docente organiza un pedido grupal. Otros se unen y piden individualmente."""
    ESTADO_CHOICES = [
        ('abierto',   'Abierto (aceptando participantes)'),
        ('cerrado',   'Cerrado / En preparación'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]

    titulo     = models.CharField(max_length=120, default='Pedido grupal sala de profes')
    organizador = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='pedidos_grupales_organizados')
    estado     = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='abierto')
    fecha      = models.DateTimeField(default=timezone.now)
    nota       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_grupal(self):
        return sum(float(p.total) for p in self.pedidos_miembros.all())

    @property
    def participantes_count(self):
        return self.pedidos_miembros.count()

    def __str__(self):
        return f'Grupal #{self.pk} — {self.titulo} [{self.get_estado_display()}]'

    class Meta:
        verbose_name = 'Pedido Grupal'
        verbose_name_plural = 'Pedidos Grupales'
        ordering = ['-fecha']


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICACIÓN DOCENTE
# ══════════════════════════════════════════════════════════════════════════════

class NotificacionDocente(models.Model):
    TIPO_CHOICES = [
        ('pedido_listo',    'Pedido Listo'),
        ('fiado_cerca',     'Límite Fiado Cerca'),
        ('pedido_grupal',   'Pedido Grupal'),
        ('info',            'Información'),
    ]

    docente    = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='notificaciones')
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES, default='info')
    titulo     = models.CharField(max_length=150)
    mensaje    = models.TextField()
    leida      = models.BooleanField(default=False)
    url_accion = models.CharField(max_length=200, blank=True)
    fecha      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.titulo}'

    class Meta:
        verbose_name = 'Notificación Docente'
        verbose_name_plural = 'Notificaciones Docente'
        ordering = ['-fecha']


# ══════════════════════════════════════════════════════════════════════════════
# RECARGA DE SALDO DOCENTE
# ══════════════════════════════════════════════════════════════════════════════

class RecargaDocente(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada',  'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    docente          = models.ForeignKey(Docente, on_delete=models.CASCADE, related_name='recargas')
    monto            = models.DecimalField(max_digits=10, decimal_places=2)
    comprobante      = models.ImageField(upload_to='recargas/docentes/', blank=True, null=True, validators=[validate_image])
    nota             = models.CharField(max_length=300, blank=True)
    estado           = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    nota_admin       = models.CharField(max_length=300, blank=True, verbose_name='Nota del administrador')
    fecha            = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Recarga ${self.monto} → {self.docente} [{self.get_estado_display()}]'

    class Meta:
        verbose_name = 'Recarga Docente'
        verbose_name_plural = 'Recargas Docente'
        ordering = ['-fecha']


# ─── HISTORIAL DE FIADO ───────────────────────────────────────────────────────

class MovimientoFiado(models.Model):
    """Registro inmutable de cada cargo o abono al fiado de un docente."""
    TIPO_CHOICES = [
        ('cargo',  'Cargo (pedido)'),
        ('abono',  'Abono (pago)'),
        ('ajuste', 'Ajuste manual'),
    ]
    docente    = models.ForeignKey(
        Docente, on_delete=models.CASCADE, related_name='movimientos_fiado'
    )
    tipo       = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto      = models.DecimalField(max_digits=10, decimal_places=2)
    saldo_post = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Deuda total del docente después del movimiento'
    )
    referencia = models.ForeignKey(
        'PedidoDocente', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movimientos_fiado',
        help_text='Pedido que originó el cargo (si aplica)'
    )
    nota       = models.TextField(blank=True)
    fecha      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_tipo_display()} ${self.monto} — {self.docente} ({self.fecha:%d/%m/%Y})'

    class Meta:
        verbose_name = 'Movimiento de Fiado'
        verbose_name_plural = 'Movimientos de Fiado'
        ordering = ['-fecha']
