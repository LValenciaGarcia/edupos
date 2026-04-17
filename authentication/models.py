from django.db import models
from django.contrib.auth.models import User


class Perfil(models.Model):
    """
    Extiende el User de Django con rol.
    Escalable: agregar nuevos roles solo requiere añadir una opción a ROL_CHOICES.
    """
    ROL_CHOICES = [
        ('admin',      'Administrador'),
        ('padre',      'Padre de Familia'),
        ('estudiante', 'Estudiante'),
        ('docente',    'Docente'),
    ]

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol        = models.CharField(max_length=20, choices=ROL_CHOICES)
    telefono   = models.CharField(max_length=20, blank=True)
    activo     = models.BooleanField(default=True)  # Admin puede desactivar cualquier cuenta
    created_at = models.DateTimeField(auto_now_add=True)

    # ── Helpers de rol ──────────────────────────────────────────────────────
    def es_admin(self):      return self.rol == 'admin'
    def es_padre(self):      return self.rol == 'padre'
    def es_estudiante(self): return self.rol == 'estudiante'
    def es_docente(self):    return self.rol == 'docente'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} [{self.get_rol_display()}]'

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfiles'


class Padre(models.Model):
    """Perfil extendido del padre. Se registra solo."""
    perfil    = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name='padre')
    documento = models.CharField(max_length=20, blank=True, verbose_name='N° documento')
    saldo     = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Saldo propio')

    def __str__(self):
        return f'Padre: {self.perfil}'

    class Meta:
        verbose_name = 'Padre de Familia'
        verbose_name_plural = 'Padres de Familia'


class Estudiante(models.Model):
    """
    Perfil extendido del estudiante.
    Solo el padre puede crear esta cuenta y vincularla.
    """
    perfil = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name='estudiante')
    padre  = models.ForeignKey(
        Padre, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='hijos'
    )
    grado    = models.CharField(max_length=10)   # Ej: "8B", "10A"
    codigo   = models.CharField(max_length=20, unique=True)  # Código estudiantil
    saldo    = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.perfil} — Grado {self.grado}'

    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'


class Docente(models.Model):
    """Perfil extendido del docente. Se registra solo."""
    perfil       = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name='docente')
    documento    = models.CharField(max_length=20, blank=True, verbose_name='N° Documento (CC)')
    materia      = models.CharField(max_length=100, blank=True, verbose_name='Materia / Área')
    saldo        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    limite_fiado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Límite de crédito (fiado)',
        help_text='Monto máximo que puede pedir sin saldo suficiente'
    )
    deuda_fiado  = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Deuda de fiado')

    @property
    def credito_disponible(self):
        return max(float(self.limite_fiado) - float(self.deuda_fiado), 0)

    @property
    def saldo_total_disponible(self):
        return float(self.saldo) + self.credito_disponible

    def __str__(self):
        return f'Docente: {self.perfil}'

    class Meta:
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'
