from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from authentication.models import Estudiante
from authentication.validators import validate_image
from decimal import Decimal
import datetime


# ─── PROVEEDOR ────────────────────────────────────────────────────────────────

class Proveedor(models.Model):
    nombre     = models.CharField(max_length=100)
    nit        = models.CharField(max_length=20, blank=True, verbose_name='NIT')
    contacto   = models.CharField(max_length=100, blank=True)
    telefono   = models.CharField(max_length=20, blank=True)
    email      = models.EmailField(blank=True)
    direccion  = models.TextField(blank=True)
    logo       = models.ImageField(upload_to='proveedores/', blank=True, null=True, validators=[validate_image])
    activo     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_compras(self):
        return self.compras.aggregate(total=models.Sum('total'))['total'] or 0

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']


# ─── CATEGORÍA ────────────────────────────────────────────────────────────────

class Categoria(models.Model):
    NOMBRE_CHOICES = [
        ('desayuno', 'Desayuno'),
        ('almuerzo', 'Almuerzo'),
        ('snacks',   'Snacks / Mecato'),
        ('bebidas',  'Bebidas'),
    ]
    nombre      = models.CharField(max_length=30, choices=NOMBRE_CHOICES, unique=True)
    descripcion = models.TextField(blank=True)
    icono       = models.CharField(max_length=10, blank=True, default='')
    activa      = models.BooleanField(default=True)

    def __str__(self):
        return self.get_nombre_display()

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'


# ─── ALÉRGENO ─────────────────────────────────────────────────────────────────

class Alergeno(models.Model):
    CODIGO_CHOICES = [
        ('gluten',    'Gluten'),
        ('lacteos',   'Lácteos'),
        ('huevo',     'Huevo'),
        ('mani',      'Maní / Cacahuate'),
        ('soya',      'Soya'),
        ('nueces',    'Frutos secos'),
        ('mariscos',  'Mariscos / Crustáceos'),
        ('pescado',   'Pescado'),
        ('mostaza',   'Mostaza'),
        ('apio',      'Apio'),
        ('sesamo',    'Sésamo'),
        ('sulfitos',  'Sulfitos'),
        ('moluscos',  'Moluscos'),
        ('otro',      'Otro'),
    ]
    codigo = models.CharField(max_length=20, choices=CODIGO_CHOICES, unique=True)
    icono  = models.CharField(max_length=10, blank=True, help_text='Emoji o clase Bootstrap Icon')

    def __str__(self):
        return self.get_codigo_display()

    class Meta:
        verbose_name = 'Alérgeno'
        verbose_name_plural = 'Alérgenos'
        ordering = ['codigo']


# ─── INGREDIENTE ──────────────────────────────────────────────────────────────

class Ingrediente(models.Model):
    UNIDAD_BASE_CHOICES = [
        ('g',        'Gramos (g)'),
        ('kg',       'Kilogramos (kg)'),
        ('ml',       'Mililitros (ml)'),
        ('l',        'Litros (l)'),
        ('und',      'Unidades'),
        ('porciones','Porciones'),
    ]

    nombre               = models.CharField(max_length=100)
    imagen               = models.ImageField(upload_to='ingredientes/', blank=True, null=True, validators=[validate_image])
    proveedor            = models.ForeignKey(
        'Proveedor', on_delete=models.PROTECT,
        related_name='ingredientes', null=True, blank=False,
        verbose_name='Proveedor principal'
    )
    # ── Unidad de compra (cómo se adquiere) ──────────────────────────────────
    unidad_compra        = models.CharField(
        max_length=50, default='und',
        help_text='Nombre de la unidad de compra (ej: bandeja, paquete, bolsa)'
    )
    contenido_por_unidad = models.DecimalField(
        max_digits=10, decimal_places=4, default=1,
        help_text='Cuántas unidades base contiene cada unidad de compra (ej: 12 huevos por bandeja)'
    )
    # ── Unidad base (cómo se consume en recetas) ─────────────────────────────
    unidad_base          = models.CharField(
        max_length=10, choices=UNIDAD_BASE_CHOICES, default='und',
        help_text='Unidad en la que se mide para recetas (ej: und, g, ml)'
    )
    # ── Alertas ───────────────────────────────────────────────────────────────
    stock_minimo         = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Alerta cuando stock_real baje de este valor (en unidades base)'
    )
    alergenos            = models.ManyToManyField(
        'Alergeno', blank=True, related_name='ingredientes',
        verbose_name='Alérgenos que contiene'
    )
    activo               = models.BooleanField(default=True)
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    # ── Propiedades derivadas ─────────────────────────────────────────────────

    @property
    def stock_real(self):
        """Stock total en unidades base — suma de lotes activos no vencidos."""
        total = self.lotes.filter(
            cantidad_base__gt=0,
            fecha_vencimiento__gte=datetime.date.today()
        ).aggregate(total=models.Sum('cantidad_base'))['total']
        return round(float(total or 0), 3)

    @property
    def costo_unitario_real(self):
        """Costo por unidad base — promedio ponderado de lotes activos."""
        lotes = list(self.lotes.filter(
            cantidad_base__gt=0,
            fecha_vencimiento__gte=datetime.date.today()
        ))
        total_base = sum(float(l.cantidad_base) for l in lotes)
        cpd = float(self.contenido_por_unidad)
        if cpd == 0:
            return 0
        if total_base == 0:
            ultimo = self.lotes.order_by('-fecha_ingreso').first()
            return round(float(ultimo.precio_compra) / cpd, 6) if ultimo else 0
        costo_total = sum(float(l.cantidad_base) * float(l.precio_compra) / cpd for l in lotes)
        return round(costo_total / total_base, 6)

    @property
    def stock_bajo(self):
        return 0 < self.stock_real <= float(self.stock_minimo)

    @property
    def sin_stock(self):
        return self.stock_real <= 0

    @property
    def lote_proximo_vencer(self):
        return self.lotes.filter(
            cantidad_base__gt=0,
            fecha_vencimiento__gte=datetime.date.today()
        ).order_by('fecha_vencimiento').first()

    @property
    def vence_pronto(self):
        lote = self.lote_proximo_vencer
        return lote is not None and (lote.fecha_vencimiento - datetime.date.today()).days <= 7

    @property
    def vencido(self):
        return self.lotes.filter(
            cantidad_base__gt=0,
            fecha_vencimiento__lt=datetime.date.today()
        ).exists()

    @property
    def dias_restantes(self):
        hace_30 = timezone.now() - datetime.timedelta(days=30)
        consumido = MovimientoIngrediente.objects.filter(
            ingrediente=self, tipo='salida', fecha__gte=hace_30
        ).aggregate(total=models.Sum('cantidad'))['total'] or 0
        if consumido == 0:
            return None
        consumo_diario = float(consumido) / 30
        return round(self.stock_real / consumo_diario) if consumo_diario > 0 else None

    def __str__(self):
        return f'{self.nombre} ({self.get_unidad_base_display()})'

    class Meta:
        verbose_name = 'Ingrediente'
        verbose_name_plural = 'Ingredientes'
        ordering = ['nombre']


# ─── LOTE DE INGREDIENTE ──────────────────────────────────────────────────────

class LoteIngrediente(models.Model):
    """Batch of an ingredient with its own expiry date and purchase price (FIFO)."""
    ingrediente           = models.ForeignKey(Ingrediente, on_delete=models.CASCADE, related_name='lotes')
    proveedor             = models.ForeignKey('Proveedor', on_delete=models.PROTECT, related_name='lotes_ingrediente')
    unidades_compra       = models.DecimalField(max_digits=10, decimal_places=2, help_text='Cantidad de unidades de compra recibidas')
    precio_compra         = models.DecimalField(max_digits=10, decimal_places=2, help_text='Precio por unidad de compra')
    cantidad_base         = models.DecimalField(max_digits=10, decimal_places=3, help_text='Stock actual en unidades base')
    cantidad_base_inicial = models.DecimalField(max_digits=10, decimal_places=3, help_text='Stock inicial en unidades base')
    fecha_vencimiento     = models.DateField()
    fecha_ingreso         = models.DateField(auto_now_add=True)
    compra                = models.ForeignKey(
        'CompraProveedor', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lotes_ingrediente'
    )
    nota                  = models.CharField(max_length=200, blank=True)

    @property
    def vencido(self):
        return self.fecha_vencimiento < datetime.date.today()

    @property
    def vence_pronto(self):
        dias = (self.fecha_vencimiento - datetime.date.today()).days
        return 0 < dias <= 7

    @property
    def dias_restantes(self):
        return (self.fecha_vencimiento - datetime.date.today()).days

    @property
    def costo_unitario_base(self):
        cpd = float(self.ingrediente.contenido_por_unidad)
        return round(float(self.precio_compra) / cpd, 6) if cpd else 0

    @property
    def subtotal_lote(self):
        return round(float(self.precio_compra) * float(self.unidades_compra), 2)

    @property
    def porcentaje_consumido(self):
        ini = float(self.cantidad_base_inicial)
        return round((1 - float(self.cantidad_base) / ini) * 100, 1) if ini else 100

    def __str__(self):
        return f'Lote {self.ingrediente.nombre} — vence {self.fecha_vencimiento}'

    class Meta:
        verbose_name = 'Lote de Ingrediente'
        verbose_name_plural = 'Lotes de Ingredientes'
        ordering = ['fecha_vencimiento']


# ─── UTILIDADES FIFO Y VENCIMIENTOS ──────────────────────────────────────────

def descontar_fifo(ingrediente, cantidad_base, nota=''):
    """Deduct cantidad_base from ingredient lots ordered by earliest expiry (FIFO).
    Must be called inside a transaction.atomic() block.
    Returns the unmet remainder (0.0 if fully covered)."""
    lotes = LoteIngrediente.objects.select_for_update().filter(
        ingrediente=ingrediente,
        cantidad_base__gt=0,
        fecha_vencimiento__gte=datetime.date.today()
    ).order_by('fecha_vencimiento')

    pendiente = Decimal(str(round(float(cantidad_base), 3)))
    for lote in lotes:
        if pendiente <= Decimal('0'):
            break
        descontar = min(lote.cantidad_base, pendiente)
        lote.cantidad_base = lote.cantidad_base - descontar
        lote.save(update_fields=['cantidad_base'])
        pendiente -= descontar

    return float(pendiente)


def verificar_lotes_vencidos():
    """Detect expired lots that still have stock and write them off as merma.
    Safe to call on every page load — idempotent."""
    lotes = LoteIngrediente.objects.filter(
        fecha_vencimiento__lt=datetime.date.today(),
        cantidad_base__gt=0
    )
    count = 0
    for lote in lotes:
        qty = lote.cantidad_base
        if float(qty) > 0:
            MovimientoIngrediente.objects.create(
                ingrediente=lote.ingrediente,
                tipo='merma',
                cantidad=qty,
                nota=f'Baja automática por vencimiento — lote {lote.fecha_vencimiento}'
            )
            lote.cantidad_base = Decimal('0')
            lote.save(update_fields=['cantidad_base'])
            count += 1
    return count


# ─── MOVIMIENTO DE INGREDIENTE ────────────────────────────────────────────────

class MovimientoIngrediente(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida',  'Salida (uso en receta)'),
        ('ajuste',  'Ajuste manual'),
        ('merma',   'Merma / Pérdida'),
    ]
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.CASCADE, related_name='movimientos')
    tipo        = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad    = models.DecimalField(max_digits=10, decimal_places=2)
    nota        = models.CharField(max_length=200, blank=True)
    compra      = models.ForeignKey(
        'CompraProveedor', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movimientos_ingrediente'
    )
    fecha       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad} {self.ingrediente.unidad_base} — {self.ingrediente.nombre}'

    class Meta:
        verbose_name = 'Movimiento de Ingrediente'
        verbose_name_plural = 'Movimientos de Ingredientes'
        ordering = ['-fecha']


# ─── PRODUCTO ─────────────────────────────────────────────────────────────────

class Producto(models.Model):
    TIPO_CHOICES = [
        ('simple',    'Simple (comprado a proveedor)'),
        ('elaborado', 'Elaborado (hecho en tienda)'),
    ]

    tipo         = models.CharField(max_length=10, choices=TIPO_CHOICES, default='simple')
    categoria    = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    nombre       = models.CharField(max_length=100)
    descripcion  = models.TextField(blank=True)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    proveedor    = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='productos'
    )
    stock        = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    imagen       = models.ImageField(upload_to='productos/', blank=True, null=True, validators=[validate_image])
    disponible   = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    @property
    def costo_calculado(self):
        if self.tipo == 'simple':
            return self.precio_costo or 0
        total = sum(float(r.cantidad) * r.ingrediente.costo_unitario_real for r in self.receta.all())
        return round(total, 2)

    @property
    def ganancia(self):
        return round(float(self.precio_venta) - float(self.costo_calculado), 2)

    @property
    def margen(self):
        if float(self.precio_venta) == 0:
            return 0
        return round((self.ganancia / float(self.precio_venta)) * 100, 1)

    @property
    def stock_bajo(self):
        return 0 < self.stock <= self.stock_minimo

    @property
    def sin_stock(self):
        return self.stock <= 0

    @property
    def dias_restantes(self):
        if self.tipo != 'simple':
            return None
        hace_30 = timezone.now() - datetime.timedelta(days=30)
        vendidos = DetallePedido.objects.filter(
            producto=self, pedido__fecha_pedido__gte=hace_30, pedido__estado='entregado'
        ).aggregate(total=models.Sum('cantidad'))['total'] or 0
        if vendidos == 0:
            return None
        consumo_diario = float(vendidos) / 30
        return round(self.stock / consumo_diario) if consumo_diario > 0 else None

    @property
    def alergenos(self):
        """Unión de alérgenos de todos los ingredientes de la receta (derivado, sin redundancia)."""
        ids = self.receta.values_list('ingrediente__alergenos', flat=True)
        return Alergeno.objects.filter(pk__in=ids).distinct()

    def esta_disponible(self):
        return self.disponible and not self.sin_stock

    def __str__(self):
        return f'{self.nombre} [{self.get_tipo_display()}]'

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['categoria', 'nombre']


# ─── RECETA ───────────────────────────────────────────────────────────────────

class RecetaIngrediente(models.Model):
    producto    = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='receta')
    ingrediente = models.ForeignKey(Ingrediente, on_delete=models.PROTECT, related_name='en_recetas')
    cantidad    = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def costo_linea(self):
        return round(float(self.cantidad) * self.ingrediente.costo_unitario_real, 4)

    def __str__(self):
        return f'{self.cantidad} {self.ingrediente.unidad_base} de {self.ingrediente.nombre} → {self.producto.nombre}'

    class Meta:
        verbose_name = 'Ingrediente de Receta'
        verbose_name_plural = 'Ingredientes de Receta'
        unique_together = ['producto', 'ingrediente']


# ─── MOVIMIENTO DE INVENTARIO ─────────────────────────────────────────────────

class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada de stock'),
        ('salida',  'Salida (venta)'),
        ('ajuste',  'Ajuste manual'),
        ('merma',   'Merma / Pérdida'),
    ]
    producto  = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='movimientos')
    tipo      = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad  = models.DecimalField(max_digits=10, decimal_places=2)
    nota      = models.CharField(max_length=200, blank=True)
    compra    = models.ForeignKey(
        'CompraProveedor', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='movimientos_producto'
    )
    fecha     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad}u — {self.producto.nombre}'

    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-fecha']


# ─── PRODUCCIÓN DE PRODUCTO ELABORADO ────────────────────────────────────────

class ProduccionElaborado(models.Model):
    """Records production of elaborated products, consuming ingredients via FIFO."""
    from django.contrib.auth import get_user_model

    producto           = models.ForeignKey('Producto', on_delete=models.PROTECT, related_name='producciones')
    cantidad_producida = models.PositiveIntegerField()
    responsable        = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, related_name='producciones'
    )
    costo_total        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nota               = models.TextField(blank=True)
    fecha              = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Prod. {self.cantidad_producida}× {self.producto.nombre} ({self.fecha.strftime("%d/%m/%Y")})'

    class Meta:
        verbose_name = 'Producción'
        verbose_name_plural = 'Producciones'
        ordering = ['-fecha']


# ─── COMPRA A PROVEEDOR ───────────────────────────────────────────────────────

class CompraProveedor(models.Model):
    proveedor  = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='compras')
    fecha      = models.DateField(default=timezone.now)
    total      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nota       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def recalcular_total(self):
        self.total = sum(d.subtotal for d in self.detalles.all())
        self.save(update_fields=['total'])

    def __str__(self):
        return f'Compra #{self.pk} — {self.proveedor} ({self.fecha})'

    class Meta:
        verbose_name = 'Compra a Proveedor'
        verbose_name_plural = 'Compras a Proveedores'
        ordering = ['-fecha']


class DetalleCompra(models.Model):
    compra          = models.ForeignKey(CompraProveedor, on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT, null=True, blank=True, related_name='compras')
    ingrediente     = models.ForeignKey(Ingrediente, on_delete=models.PROTECT, null=True, blank=True, related_name='compras')
    cantidad        = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=4)

    def clean(self):
        tiene_prod = self.producto_id is not None
        tiene_ing  = self.ingrediente_id is not None
        if not tiene_prod and not tiene_ing:
            raise ValidationError('Debes indicar un producto o un ingrediente.')
        if tiene_prod and tiene_ing:
            raise ValidationError('Un detalle de compra no puede referenciar producto e ingrediente al mismo tiempo.')

    @property
    def subtotal(self):
        return round(float(self.cantidad) * float(self.precio_unitario), 2)

    def __str__(self):
        return f'{self.cantidad} × {self.producto or self.ingrediente}'

    class Meta:
        verbose_name = 'Detalle de Compra'
        verbose_name_plural = 'Detalles de Compra'


# ─── PEDIDO ───────────────────────────────────────────────────────────────────

class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('preparando', 'En preparación'),
        ('listo',      'Listo para recoger'),
        ('entregado',  'Entregado'),
        ('cancelado',  'Cancelado'),
    ]

    ticket        = models.CharField(max_length=20, unique=True, editable=False)
    estudiante    = models.ForeignKey(Estudiante, on_delete=models.PROTECT, related_name='pedidos')
    estado        = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    total         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    costo_total   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    nota          = models.TextField(blank=True)
    fecha_pedido  = models.DateTimeField(default=timezone.now)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.ticket:
            with transaction.atomic():
                año = timezone.now().year
                ultimo = (
                    Pedido.objects
                    .select_for_update()
                    .filter(ticket__startswith=f'PA-{año}-')
                    .order_by('-ticket')
                    .first()
                )
                num = (int(ultimo.ticket.split('-')[-1]) + 1) if ultimo else 1
                self.ticket = f'PA-{año}-{num:05d}'
                super().save(*args, **kwargs)
                return
        super().save(*args, **kwargs)

    def recalcular_totales(self):
        detalles = self.detalles.all()
        self.total = sum(float(d.subtotal) for d in detalles) if detalles else 0
        self.costo_total = sum(float(d.costo_linea) for d in detalles) if detalles else 0
        self.save(update_fields=['total', 'costo_total'])

    @property
    def ganancia(self):
        return round(float(self.total) - float(self.costo_total), 2)

    def __str__(self):
        return f'{self.ticket} — {self.estudiante} [{self.get_estado_display()}]'

    class Meta:
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['-fecha_pedido']


class DetallePedido(models.Model):
    pedido          = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles')
    cantidad        = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    costo_unitario  = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def subtotal(self):
        return round(float(self.cantidad) * float(self.precio_unitario), 2)

    @property
    def costo_linea(self):
        return round(float(self.cantidad) * float(self.costo_unitario), 2)

    @property
    def ganancia_linea(self):
        return round(self.subtotal - self.costo_linea, 2)

    def save(self, *args, **kwargs):
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio_venta
        # Siempre actualizar costo_unitario con el valor actual del producto (para que sea exacto en el momento de la venta)
        if not self.costo_unitario or self.costo_unitario == 0:
            self.costo_unitario = self.producto.costo_calculado
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.cantidad}× {self.producto.nombre} en {self.pedido.ticket}'

    class Meta:
        verbose_name = 'Detalle de Pedido'
        verbose_name_plural = 'Detalles de Pedido'


# ─── INSUMO ───────────────────────────────────────────────────────────────────

class Insumo(models.Model):
    """Materiales de uso operacional (servilletas, cucharas, vasos, etc.).
    No forman parte de recetas ni afectan el costo de productos."""

    CATEGORIA_CHOICES = [
        ('desechables',  'Desechables'),
        ('limpieza',     'Limpieza'),
        ('empaque',      'Empaque'),
        ('utensilio',    'Utensilio'),
        ('otro',         'Otro'),
    ]
    UNIDAD_CHOICES = [
        ('und',    'Unidades'),
        ('paquete','Paquetes'),
        ('caja',   'Cajas'),
        ('rollo',  'Rollos'),
        ('kg',     'Kilogramos'),
        ('l',      'Litros'),
    ]

    nombre          = models.CharField(max_length=100)
    categoria       = models.CharField(max_length=15, choices=CATEGORIA_CHOICES, default='otro')
    unidad          = models.CharField(max_length=10, choices=UNIDAD_CHOICES, default='und')
    imagen          = models.ImageField(upload_to='insumos/', blank=True, null=True, validators=[validate_image])
    descripcion     = models.TextField(blank=True)
    stock           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock_minimo    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio_unitario = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Precio de referencia por unidad'
    )
    proveedor       = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='insumos'
    )
    activo          = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    @property
    def stock_bajo(self):
        return float(self.stock) <= float(self.stock_minimo)

    @property
    def sin_stock(self):
        return float(self.stock) <= 0

    def __str__(self):
        return f'{self.nombre} ({self.get_unidad_display()})'

    class Meta:
        verbose_name = 'Insumo'
        verbose_name_plural = 'Insumos'
        ordering = ['categoria', 'nombre']


class MovimientoInsumo(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('salida',  'Consumo'),
        ('ajuste',  'Ajuste manual'),
        ('merma',   'Merma / Pérdida'),
    ]
    insumo   = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name='movimientos')
    tipo     = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    nota     = models.CharField(max_length=200, blank=True)
    fecha    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad} {self.insumo.unidad} — {self.insumo.nombre}'

    class Meta:
        verbose_name = 'Movimiento de Insumo'
        verbose_name_plural = 'Movimientos de Insumos'
        ordering = ['-fecha']


# ─── PERFIL ADMIN ─────────────────────────────────────────────────────────────

class PerfilAdmin(models.Model):
    """Datos extendidos del administrador de la cafetería."""
    perfil           = models.OneToOneField(
        'authentication.Perfil', on_delete=models.CASCADE,
        related_name='perfil_admin'
    )
    documento        = models.CharField(max_length=20, blank=True, verbose_name='N° Documento (CC)')
    telefono         = models.CharField(max_length=20, blank=True)
    direccion        = models.CharField(max_length=200, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    foto             = models.ImageField(upload_to='perfiles/', blank=True, null=True, validators=[validate_image])
    cargo            = models.CharField(max_length=100, blank=True, default='Administrador de Cafetería')

    def __str__(self):
        return f'Perfil Admin — {self.perfil}'

    class Meta:
        verbose_name = 'Perfil Administrador'
        verbose_name_plural = 'Perfiles Administrador'


# ─── GOOGLE CALENDAR ──────────────────────────────────────────────────────────

class GoogleCalendarToken(models.Model):
    """Token OAuth2 de Google Calendar vinculado a un PerfilAdmin."""
    admin         = models.OneToOneField(
        PerfilAdmin, on_delete=models.CASCADE, related_name='gcal'
    )
    access_token  = models.TextField()
    refresh_token = models.TextField(blank=True)
    token_expiry  = models.DateTimeField(null=True, blank=True)
    gcal_id       = models.CharField(max_length=300, default='primary',
                                     help_text='ID del calendario de Google (se asigna automáticamente)')
    synced_at     = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'GCal token — {self.admin}'

    class Meta:
        verbose_name = 'Token Google Calendar'
        verbose_name_plural = 'Tokens Google Calendar'
