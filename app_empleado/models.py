from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from authentication.models import Empleado, Sede, Estudiante, Docente
from app_admin.models import Producto


class TurnoCaja(models.Model):
    ESTADO_CHOICES = [
        ('abierto', 'Abierto'),
        ('cerrado', 'Cerrado'),
    ]
    empleado         = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name='turnos')
    sede             = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='turnos')
    estado           = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='abierto')
    apertura         = models.DateTimeField(default=timezone.now)
    cierre           = models.DateTimeField(null=True, blank=True)
    efectivo_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    efectivo_final   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    nota             = models.TextField(blank=True)

    @property
    def duracion_str(self):
        fin = self.cierre or timezone.now()
        delta = fin - self.apertura
        h = int(delta.total_seconds() // 3600)
        m = int((delta.total_seconds() % 3600) // 60)
        return f'{h}h {m}m'

    @property
    def total_ventas(self):
        from django.db.models import Sum
        return self.ventas_turno.filter(anulada=False).aggregate(
            t=Sum('total')
        )['t'] or 0

    @property
    def num_ventas(self):
        return self.ventas_turno.filter(anulada=False).count()

    @property
    def total_efectivo(self):
        from django.db.models import Sum
        return self.ventas_turno.filter(anulada=False, tipo_pago='efectivo').aggregate(
            t=Sum('total')
        )['t'] or 0

    def __str__(self):
        return f'Turno #{self.pk} — {self.empleado} ({self.apertura.date()})'

    class Meta:
        verbose_name = 'Turno de Caja'
        verbose_name_plural = 'Turnos de Caja'
        ordering = ['-apertura']


class VentaEmpleado(models.Model):
    TIPO_PAGO_CHOICES = [
        ('efectivo',          'Efectivo'),
        ('cuenta_estudiante', 'Cuenta Estudiante'),
        ('cuenta_docente',    'Cuenta Docente'),
    ]

    ticket      = models.CharField(max_length=20, unique=True, editable=False)
    empleado    = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name='ventas')
    sede        = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name='ventas')
    turno       = models.ForeignKey(
        TurnoCaja, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ventas_turno'
    )
    tipo_pago   = models.CharField(max_length=20, choices=TIPO_PAGO_CHOICES, default='efectivo')
    estudiante  = models.ForeignKey(
        Estudiante, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ventas_empleado'
    )
    docente     = models.ForeignKey(
        Docente, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ventas_empleado'
    )
    total       = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fiado_usado = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                      help_text='Monto cargado a fiado en ventas de docente')
    anulada     = models.BooleanField(default=False)
    fecha       = models.DateTimeField(default=timezone.now)
    nota        = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.ticket:
            año  = timezone.now().year
            last = VentaEmpleado.objects.filter(ticket__startswith=f'VE-{año}-').order_by('-ticket').first()
            num  = (int(last.ticket.split('-')[-1]) + 1) if last else 1
            self.ticket = f'VE-{año}-{num:05d}'
        super().save(*args, **kwargs)

    def recalcular_total(self):
        self.total = sum(float(d.subtotal) for d in self.detalles.all())
        self.save(update_fields=['total'])

    def __str__(self):
        return f'{self.ticket} [{self.get_tipo_pago_display()}]{"  [ANULADA]" if self.anulada else ""}'

    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-fecha']


class DetalleVenta(models.Model):
    venta       = models.ForeignKey(VentaEmpleado, on_delete=models.CASCADE, related_name='detalles')
    producto    = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_venta')
    cantidad    = models.PositiveIntegerField(default=1)
    precio_unit = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return round(float(self.cantidad) * float(self.precio_unit), 2)

    def __str__(self):
        return f'{self.cantidad}x {self.producto.nombre}'

    class Meta:
        verbose_name = 'Detalle de Venta'
        verbose_name_plural = 'Detalles de Venta'


class AnulacionVenta(models.Model):
    venta           = models.OneToOneField(VentaEmpleado, on_delete=models.CASCADE, related_name='anulacion')
    supervisor_user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='anulaciones_autorizadas'
    )
    motivo          = models.TextField()
    fecha           = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Anulación {self.venta.ticket} — supervisor: {self.supervisor_user.username}'

    class Meta:
        verbose_name = 'Anulación de Venta'
        verbose_name_plural = 'Anulaciones de Venta'
        ordering = ['-fecha']
