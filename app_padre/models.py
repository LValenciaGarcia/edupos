from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from authentication.models import Estudiante, Padre
from authentication.validators import validate_image
from app_admin.models import Producto, Categoria
from simple_history.models import HistoricalRecords


# ══════════════════════════════════════════════════════════════════════════════
# RECARGA DE SALDO (con flujo de validación)
# ══════════════════════════════════════════════════════════════════════════════

class RecargaSaldo(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada',  'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    estudiante       = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='recargas')
    padre            = models.ForeignKey(Padre, on_delete=models.SET_NULL, null=True, related_name='recargas_realizadas')
    monto            = models.DecimalField(max_digits=10, decimal_places=2)
    comprobante      = models.ImageField(upload_to='recargas/comprobantes/', blank=True, null=True, validators=[validate_image])
    nota             = models.CharField(max_length=300, blank=True)
    estado           = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    nota_admin       = models.CharField(max_length=300, blank=True, verbose_name='Nota del administrador')
    fecha            = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    history          = HistoricalRecords()

    @transaction.atomic
    def aprobar(self):
        from decimal import Decimal
        # Lock ambos registros para evitar race conditions
        recarga = RecargaSaldo.objects.select_for_update().get(pk=self.pk)
        if recarga.estado != 'pendiente':
            return  # Ya fue procesada, no hacer nada
        estudiante = Estudiante.objects.select_for_update().get(pk=recarga.estudiante.pk)

        recarga.estado = 'aprobada'
        recarga.fecha_resolucion = timezone.now()
        recarga.save(update_fields=['estado', 'fecha_resolucion'])

        estudiante.saldo += Decimal(str(recarga.monto))
        estudiante.save(update_fields=['saldo'])

        # Actualizar atributos de self para reflejar cambios
        self.estado = recarga.estado
        self.fecha_resolucion = recarga.fecha_resolucion

        Notificacion.objects.create(
            padre=recarga.padre,
            tipo='recarga_aprobada',
            titulo='Recarga aprobada',
            mensaje=f'Tu recarga de ${recarga.monto:,.0f} para {estudiante.perfil.user.get_full_name()} fue aprobada.',
            url_accion='/padre/hijos/',
        )

    @transaction.atomic
    def rechazar(self, nota=''):
        recarga = RecargaSaldo.objects.select_for_update().get(pk=self.pk)
        if recarga.estado != 'pendiente':
            return  # Ya fue procesada
        recarga.estado = 'rechazada'
        recarga.nota_admin = nota
        recarga.fecha_resolucion = timezone.now()
        recarga.save(update_fields=['estado', 'nota_admin', 'fecha_resolucion'])

        self.estado = recarga.estado
        self.fecha_resolucion = recarga.fecha_resolucion

        Notificacion.objects.create(
            padre=recarga.padre,
            tipo='recarga_rechazada',
            titulo='Recarga rechazada',
            mensaje=f'Tu recarga de ${recarga.monto:,.0f} para {recarga.estudiante.perfil.user.get_full_name()} fue rechazada. {nota}'.strip(),
            url_accion='/padre/hijos/',
        )

    def __str__(self):
        return f'Recarga ${self.monto} → {self.estudiante} [{self.get_estado_display()}]'

    class Meta:
        verbose_name = 'Recarga de Saldo'
        verbose_name_plural = 'Recargas de Saldo'
        ordering = ['-fecha']


# ══════════════════════════════════════════════════════════════════════════════
# LÍMITES DE GASTO
# ══════════════════════════════════════════════════════════════════════════════

class LimiteGasto(models.Model):
    TIPO_CHOICES = [
        ('diario',   'Diario'),
        ('semanal',  'Semanal'),
        ('mensual',  'Mensual'),
    ]

    padre      = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='limites')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='limites')
    tipo       = models.CharField(max_length=10, choices=TIPO_CHOICES)
    monto      = models.DecimalField(max_digits=10, decimal_places=2)
    activo     = models.BooleanField(default=True)

    def gasto_actual(self):
        """Gasto acumulado del estudiante en el periodo, incluyendo pedidos en curso."""
        from app_admin.models import Pedido
        ahora = timezone.now()
        if self.tipo == 'diario':
            inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.tipo == 'semanal':
            inicio = ahora - timezone.timedelta(days=ahora.weekday())
            inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Incluye pendiente/preparando/listo para evitar bypass con pedidos simultáneos
        return Pedido.objects.filter(
            estudiante=self.estudiante,
            estado__in=['pendiente', 'preparando', 'listo', 'entregado'],
            fecha_pedido__gte=inicio,
        ).aggregate(t=models.Sum('total'))['t'] or 0

    @property
    def porcentaje_uso(self):
        if float(self.monto) == 0:
            return 0
        return min(round((float(self.gasto_actual()) / float(self.monto)) * 100), 100)

    @property
    def disponible(self):
        return max(float(self.monto) - float(self.gasto_actual()), 0)

    def __str__(self):
        return f'Límite {self.get_tipo_display()} ${self.monto} — {self.estudiante}'

    class Meta:
        verbose_name = 'Límite de Gasto'
        verbose_name_plural = 'Límites de Gasto'
        unique_together = ['padre', 'estudiante', 'tipo']


# ══════════════════════════════════════════════════════════════════════════════
# ALERGIAS
# ══════════════════════════════════════════════════════════════════════════════

class AlergiaEstudiante(models.Model):
    """Alergias o intolerancias alimenticias registradas por el padre."""
    TIPO_CHOICES = [
        ('alergia',      'Alergia'),
        ('intolerancia', 'Intolerancia'),
        ('sensibilidad', 'Sensibilidad'),
    ]
    GRAVEDAD_CHOICES = [
        ('leve',    'Leve'),
        ('moderada','Moderada'),
        ('severa',  'Severa / Anafilaxia'),
    ]

    padre      = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='alergias')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='alergias')
    nombre     = models.CharField(max_length=100, help_text='Ej: Maní, Lactosa, Gluten, Mariscos…')
    tipo       = models.CharField(max_length=15, choices=TIPO_CHOICES, default='alergia')
    gravedad   = models.CharField(max_length=12, choices=GRAVEDAD_CHOICES, default='leve')
    notas      = models.TextField(blank=True, help_text='Síntomas, medicación, instrucciones de emergencia…')
    activo     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.nombre} ({self.get_gravedad_display()}) — {self.estudiante}'

    class Meta:
        verbose_name = 'Alergia de Estudiante'
        verbose_name_plural = 'Alergias de Estudiantes'
        ordering = ['-gravedad', 'nombre']
        unique_together = ['estudiante', 'nombre', 'tipo']


# ══════════════════════════════════════════════════════════════════════════════
# RESTRICCIONES ALIMENTICIAS
# ══════════════════════════════════════════════════════════════════════════════

class RestriccionAlimento(models.Model):
    padre      = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='restricciones')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, null=True, blank=True, related_name='restricciones')
    producto   = models.ForeignKey(Producto, on_delete=models.CASCADE, null=True, blank=True, related_name='restricciones')
    categoria  = models.ForeignKey(Categoria, on_delete=models.CASCADE, null=True, blank=True, related_name='restricciones')
    motivo     = models.CharField(max_length=200, blank=True)
    activo     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        tiene_prod = self.producto_id is not None
        tiene_cat  = self.categoria_id is not None
        if not tiene_prod and not tiene_cat:
            raise ValidationError('Debes indicar un producto o una categoría a restringir.')
        if tiene_prod and tiene_cat:
            raise ValidationError('Una restricción no puede referenciar producto y categoría al mismo tiempo.')

    def __str__(self):
        obj = self.producto or self.categoria
        est = self.estudiante or 'todos los hijos'
        return f'Restricción: {obj} para {est}'

    class Meta:
        verbose_name = 'Restricción Alimenticia'
        verbose_name_plural = 'Restricciones Alimenticias'
        ordering = ['-created_at']


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICACIONES
# ══════════════════════════════════════════════════════════════════════════════

class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('recarga_aprobada',  'Recarga Aprobada'),
        ('recarga_rechazada', 'Recarga Rechazada'),
        ('recarga_pendiente', 'Recarga Pendiente'),
        ('limite_cerca',      'Límite Cerca'),
        ('limite_superado',   'Límite Superado'),
        ('compra_realizada',  'Compra Realizada'),
        ('compra_bloqueada',  'Compra Bloqueada'),
        ('pedido_padre',      'Pedido del Padre'),
        ('saldo_bajo',        'Saldo Bajo'),
        ('info',              'Información'),
    ]

    padre      = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='notificaciones')
    tipo       = models.CharField(max_length=25, choices=TIPO_CHOICES, default='info')
    titulo     = models.CharField(max_length=150)
    mensaje    = models.TextField()
    leida      = models.BooleanField(default=False)
    url_accion = models.CharField(max_length=200, blank=True)
    fecha      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.titulo}'

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha']


# ══════════════════════════════════════════════════════════════════════════════
# HORARIOS DE COMPRA
# ══════════════════════════════════════════════════════════════════════════════

class HorarioCompra(models.Model):
    DIAS_CHOICES = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes'),
    ]

    padre         = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='horarios')
    estudiante    = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='horarios')
    nombre        = models.CharField(max_length=80, default='Recreo')
    hora_inicio   = models.TimeField()
    hora_fin      = models.TimeField()
    activo        = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.nombre}: {self.hora_inicio}–{self.hora_fin} ({self.estudiante})'

    class Meta:
        verbose_name = 'Horario de Compra'
        verbose_name_plural = 'Horarios de Compra'
        ordering = ['hora_inicio']


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS DEL PADRE
# ══════════════════════════════════════════════════════════════════════════════

class PedidoPadre(models.Model):
    FUENTE_CHOICES = [
        ('saldo_hijo',  'Saldo del hijo'),
        ('saldo_padre', 'Saldo del padre'),
    ]

    pedido     = models.OneToOneField('app_admin.Pedido', on_delete=models.CASCADE, related_name='pedido_padre')
    padre      = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='pedidos_realizados')
    fuente     = models.CharField(max_length=15, choices=FUENTE_CHOICES, default='saldo_hijo')
    nota       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Pedido padre {self.padre} → {self.pedido.ticket}'

    class Meta:
        verbose_name = 'Pedido del Padre'
        verbose_name_plural = 'Pedidos del Padre'
        ordering = ['-created_at']


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDO PROGRAMADO
# ══════════════════════════════════════════════════════════════════════════════

class PedidoProgramado(models.Model):
    ESTADO_CHOICES = [
        ('activo',     'Activo'),
        ('procesado',  'Procesado'),
        ('cancelado',  'Cancelado'),
    ]

    padre         = models.ForeignKey(Padre, on_delete=models.CASCADE, related_name='pedidos_programados')
    estudiante    = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='pedidos_programados')
    fecha_entrega = models.DateField()
    hora_entrega  = models.TimeField(null=True, blank=True)
    fuente        = models.CharField(max_length=15, choices=PedidoPadre.FUENTE_CHOICES, default='saldo_hijo')
    nota          = models.TextField(blank=True)
    estado        = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='activo')
    pedido        = models.ForeignKey('app_admin.Pedido', on_delete=models.SET_NULL, null=True, blank=True, related_name='programados')
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Programado {self.fecha_entrega} — {self.estudiante}'

    class Meta:
        verbose_name = 'Pedido Programado'
        verbose_name_plural = 'Pedidos Programados'
        ordering = ['fecha_entrega']


class DetalleProgramado(models.Model):
    pedido_prog     = models.ForeignKey(PedidoProgramado, on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad        = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Precio congelado al momento de programar el pedido'
    )

    def save(self, *args, **kwargs):
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_venta
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return float(self.cantidad) * float(self.precio_unitario)

    def __str__(self):
        return f'{self.cantidad}× {self.producto.nombre}'

    class Meta:
        verbose_name = 'Detalle Pedido Programado'
        verbose_name_plural = 'Detalles Pedidos Programados'
