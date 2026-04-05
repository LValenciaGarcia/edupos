from django.db import models
from authentication.models import Estudiante, Padre


class RecargaSaldo(models.Model):
    estudiante = models.ForeignKey(
        Estudiante, on_delete=models.CASCADE, related_name='recargas'
    )
    padre = models.ForeignKey(
        Padre, on_delete=models.SET_NULL,
        null=True, related_name='recargas_realizadas'
    )
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    nota  = models.CharField(max_length=200, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Recarga ${self.monto} → {self.estudiante} ({self.fecha.date()})'

    class Meta:
        verbose_name = 'Recarga de Saldo'
        verbose_name_plural = 'Recargas de Saldo'
        ordering = ['-fecha']
