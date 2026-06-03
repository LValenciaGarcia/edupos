from django.db import models, transaction
from django.utils import timezone
from authentication.models import Estudiante
from simple_history.models import HistoricalRecords

ESTADO_RECARGA_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('aprobada',  'Aprobada'),
    ('rechazada', 'Rechazada'),
]


class RecargaEstudiante(models.Model):
    """Recarga de saldo iniciada por el propio estudiante vía MercadoPago.
    Solo disponible cuando Estudiante.puede_recargar_autonomo == True."""

    estudiante       = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='recargas_propias')
    monto            = models.DecimalField(max_digits=10, decimal_places=2)
    nota             = models.CharField(max_length=300, blank=True)
    estado           = models.CharField(max_length=15, choices=ESTADO_RECARGA_CHOICES, default='pendiente')
    mp_preference_id = models.CharField(max_length=200, blank=True)
    mp_payment_id    = models.CharField(max_length=100, blank=True)
    nota_admin       = models.CharField(max_length=300, blank=True)
    fecha            = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    history          = HistoricalRecords()

    @transaction.atomic
    def aprobar(self):
        from decimal import Decimal
        recarga = RecargaEstudiante.objects.select_for_update().get(pk=self.pk)
        if recarga.estado != 'pendiente':
            return
        estudiante = Estudiante.objects.select_for_update().get(pk=recarga.estudiante.pk)
        recarga.estado = 'aprobada'
        recarga.fecha_resolucion = timezone.now()
        recarga.save(update_fields=['estado', 'fecha_resolucion'])
        estudiante.saldo += Decimal(str(recarga.monto))
        estudiante.save(update_fields=['saldo'])
        self.estado = recarga.estado
        self.fecha_resolucion = recarga.fecha_resolucion
        if estudiante.padre:
            from app_padre.models import Notificacion
            nombre = estudiante.perfil.user.get_full_name() or estudiante.codigo
            Notificacion.objects.create(
                padre=estudiante.padre,
                tipo='recarga_aprobada',
                titulo='Recarga autónoma aprobada',
                mensaje=f'{nombre} recargó su propio saldo por ${recarga.monto:,.0f} vía MercadoPago.',
                url_accion='/padre/hijos/',
            )

    @transaction.atomic
    def rechazar(self, nota=''):
        recarga = RecargaEstudiante.objects.select_for_update().get(pk=self.pk)
        if recarga.estado != 'pendiente':
            return
        recarga.estado = 'rechazada'
        recarga.nota_admin = nota
        recarga.fecha_resolucion = timezone.now()
        recarga.save(update_fields=['estado', 'nota_admin', 'fecha_resolucion'])
        self.estado = recarga.estado
        self.fecha_resolucion = recarga.fecha_resolucion
        if recarga.estudiante.padre:
            from app_padre.models import Notificacion
            nombre = recarga.estudiante.perfil.user.get_full_name() or recarga.estudiante.codigo
            Notificacion.objects.create(
                padre=recarga.estudiante.padre,
                tipo='recarga_rechazada',
                titulo='Recarga autónoma rechazada',
                mensaje=f'La recarga autónoma de {nombre} por ${recarga.monto:,.0f} fue rechazada. {nota}'.strip(),
                url_accion='/padre/hijos/',
            )

    def __str__(self):
        return f'Recarga estudiante ${self.monto} → {self.estudiante} [{self.get_estado_display()}]'

    class Meta:
        verbose_name = 'Recarga de Estudiante'
        verbose_name_plural = 'Recargas de Estudiantes'
        ordering = ['-fecha']
