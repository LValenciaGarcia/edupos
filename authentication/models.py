from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords


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
        ('empleado',   'Empleado'),
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
    def es_empleado(self):   return self.rol == 'empleado'

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
    grado    = models.CharField(max_length=10)
    codigo   = models.CharField(max_length=20, unique=True)
    saldo    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    puede_recargar_autonomo = models.BooleanField(
        default=False,
        verbose_name='Puede recargar autónomamente',
        help_text='El padre puede habilitar que el estudiante recargue su saldo directamente con MercadoPago.',
    )
    huella_template    = models.BinaryField(null=True, blank=True, editable=False)
    huella_enrolada_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords()

    @property
    def tiene_huella(self):
        return self.huella_template is not None and len(self.huella_template) > 0

    def __str__(self):
        return f'{self.perfil} — Grado {self.grado}'

    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'


class Docente(models.Model):
    """Perfil extendido del docente. Se registra solo."""
    perfil    = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name='docente')
    documento = models.CharField(max_length=20, blank=True, verbose_name='N° Documento (CC)')
    materia   = models.CharField(max_length=100, blank=True, verbose_name='Materia / Área')
    saldo     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    huella_template    = models.BinaryField(null=True, blank=True, editable=False)
    huella_enrolada_at = models.DateTimeField(null=True, blank=True)
    history   = HistoricalRecords()

    @property
    def tiene_huella(self):
        return self.huella_template is not None and len(self.huella_template) > 0

    def __str__(self):
        return f'Docente: {self.perfil}'

    class Meta:
        verbose_name = 'Docente'
        verbose_name_plural = 'Docentes'


# ─── SEDE ─────────────────────────────────────────────────────────────────────

class Sede(models.Model):
    """Sede física (sucursal) de la cafetería."""
    nombre    = models.CharField(max_length=100, unique=True)
    direccion = models.CharField(max_length=200, blank=True)
    ciudad    = models.CharField(max_length=100, default='Cali')
    activa    = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'
        ordering = ['nombre']


# ─── EMPLEADO ─────────────────────────────────────────────────────────────────

class Empleado(models.Model):
    """
    Perfil extendido del empleado de tienda.
    Creado exclusivamente por el Administrador; las credenciales se generan automáticamente.
    """
    CARGO_CHOICES = [
        ('cajero',     'Cajero'),
        ('atencion',   'Atención al Cliente'),
        ('supervisor', 'Supervisor de Sede'),
    ]

    perfil    = models.OneToOneField(Perfil, on_delete=models.CASCADE, related_name='empleado')
    documento = models.CharField(max_length=20, blank=True, verbose_name='N° Documento')
    cargo     = models.CharField(max_length=20, choices=CARGO_CHOICES, default='cajero')
    sedes     = models.ManyToManyField(Sede, related_name='empleados', blank=True)
    es_global = models.BooleanField(
        default=False,
        verbose_name='Acceso global',
        help_text='Puede visualizar información consolidada de todas las sedes'
    )
    history = HistoricalRecords()

    def __str__(self):
        return f'Empleado: {self.perfil}'

    class Meta:
        verbose_name = 'Empleado'
        verbose_name_plural = 'Empleados'
