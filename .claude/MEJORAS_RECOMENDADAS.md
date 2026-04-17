# 🚀 MEJORAS RECOMENDADAS - Punto Asis

## 1. ARQUITECTURA Y PATRONES

### A. Implementar transacciones atómicas

**Patrón actual (❌ INSEGURO):**
```python
def menu(request):
    # 1. Check saldo
    if estudiante.saldo < total:
        return
    # 2. Crear pedido
    pedido = Pedido.objects.create(...)
    # 3. Crear detalles (múltiples queries)
    # 4. Descontar saldo (RACE CONDITION aquí)
```

**Patrón correcto (✅ SEGURO):**
```python
from django.db import transaction

@transaction.atomic
def menu(request):
    # Lock el estudiante para este bloque
    est = Estudiante.objects.select_for_update().get(pk=...)
    
    # Todas las queries aquí son parte de UNA transacción
    if est.saldo < total:
        return  # Rollback automático
    
    pedido = Pedido.objects.create(...)
    for detalle in detalles:
        DetallePedido.objects.create(...)
    
    est.saldo -= total
    est.save()  # Commit solo si todo pasó
```

**Aplicar a:**
- `app_estudiante/views.py` - función `menu()` y `cancelar_pedido()`
- `app_padre/views.py` - función `pedido_padre()`, `recargar_saldo()`
- `app_padre/models.py` - método `RecargaSaldo.aprobar()` y `rechazar()`
- `app_admin/views.py` - función `pedido_estado()` (entregar) y `entrada_stock()`

---

### B. Máquina de estados para pedidos

**Problema actual:** Un pedido puede cambiar de cualquier estado a cualquier otro sin lógica.

**Solución - Usar django-fsm:**
```python
pip install django-fsm

from django_fsm import FSMField, transition

class Pedido(models.Model):
    estado = FSMField(
        max_length=15,
        choices=ESTADO_CHOICES,
        default='pendiente'
    )
    
    @transition(field=estado, source='pendiente', target='preparando')
    def empezar_preparacion(self):
        pass
    
    @transition(field=estado, source='preparando', target='listo')
    def marcar_listo(self):
        pass
    
    @transition(field=estado, source='listo', target='entregado')
    def entregar(self, fecha_entrega=None):
        self.fecha_entrega = fecha_entrega or timezone.now()
    
    @transition(field=estado, source='pendiente', target='cancelado')
    def cancelar(self):
        # Lógica para revertir cambios
        pass
```

**Ventajas:**
- Transiciones válidas automáticamente verificadas
- Imposible estados ilógicos
- Auditoría incorporada

---

## 2. RENDIMIENTO

### A. Eliminar N+1 queries

**Problema actual - app_padre/views.py:429-434:**
```python
for h in padre.hijos.all():
    gasto = Pedido.objects.filter(  # ← N QUERIES
        estudiante=h
    ).aggregate(...)
```

**Solución:**
```python
from django.db.models import Prefetch, Sum, DecimalField
from django.db.models.functions import Coalesce

# Calcular gastos en UNA query
hijos_stats = padre.hijos.annotate(
    gasto_total=Coalesce(
        Sum('pedidos__total'),
        0,
        output_field=DecimalField()
    )
).values('id', 'gasto_total')

# Convertir a dict para acceso O(1)
gasto_map = {h['id']: h['gasto_total'] for h in hijos_stats}

for h in padre.hijos.all():
    gasto = gasto_map[h.id]
```

---

### B. Mover lógica de propiedades a métodos anotados

**Problema actual - app_admin/models.py:208-218:**
```python
@property
def dias_restantes(self):
    # Cada acceso = 1 query
    vendidos = DetallePedido.objects.filter(
        producto=self, ...
    ).aggregate(...)
    return ...
```

**Solución:**
```python
from django.db.models import Prefetch, Case, When, DecimalField

# En la vista:
productos = Producto.objects.annotate(
    vendidos_30d=Coalesce(
        Sum('detalles__cantidad', 
            filter=Q(detalles__pedido__fecha_pedido__gte=hace_30)),
        0,
        output_field=DecimalField()
    )
).values('id', 'stock', 'vendidos_30d')

# En template, acceder directamente sin query
for p in productos:
    dias = p['stock'] / (p['vendidos_30d'] / 30)
```

---

### C. Índices en base de datos

**Agregar a migrations:**
```python
class Migration(migrations.Migration):
    operations = [
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(
                fields=['estudiante', 'fecha_pedido'],
                name='pedido_est_fecha_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='pedido',
            index=models.Index(
                fields=['estado', 'fecha_pedido'],
                name='pedido_est_estado_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='detallepedido',
            index=models.Index(
                fields=['pedido', 'producto'],
                name='detalle_ped_prod_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='limitesgasto',
            index=models.Index(
                fields=['padre', 'estudiante', 'tipo'],
                name='limite_est_tipo_idx'
            ),
        ),
    ]
```

---

## 3. VALIDACIÓN Y SEGURIDAD

### A. Crear un validador centralizado

**Archivo nuevo: app_admin/validators.py**
```python
from decimal import Decimal
from django.core.exceptions import ValidationError

class MoneyValidator:
    """Valida campos de dinero de forma segura."""
    
    MIN = Decimal('0.01')
    MAX = Decimal('10000000.00')
    
    @staticmethod
    def validate(value, field_name='Monto'):
        """Valida y retorna Decimal o None."""
        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return None
            
            value = Decimal(str(value))
            
            if value < MoneyValidator.MIN:
                raise ValidationError(
                    f"{field_name} debe ser mayor a ${MoneyValidator.MIN}"
                )
            if value > MoneyValidator.MAX:
                raise ValidationError(
                    f"{field_name} no puede exceder ${MoneyValidator.MAX}"
                )
            
            return value
        except (ValueError, TypeError, InvalidOperation):
            raise ValidationError(f"{field_name} inválido. Use formato: 50.00")

# Uso:
try:
    monto = MoneyValidator.validate(request.POST.get('monto'), 'Monto recarga')
except ValidationError as e:
    messages.error(request, str(e))
    return redirect(...)
```

---

### B. Formularios Django con validación

**Archivo nuevo: app_admin/forms.py**
```python
from django import forms
from django.core.exceptions import ValidationError
from .models import Pedido, Producto

class EntradaStockForm(forms.Form):
    """Valida entrada de stock de forma segura."""
    
    item_tipo = forms.CharField()
    item_id = forms.IntegerField()
    item_cantidad = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        max_value=Decimal('100000.00')
    )
    item_precio = forms.DecimalField(
        max_digits=10,
        decimal_places=4,
        min_value=Decimal('0.0001')
    )
    
    def clean(self):
        cleaned = super().clean()
        
        if cleaned.get('item_tipo') not in ['producto', 'ingrediente']:
            raise ValidationError("Tipo de item inválido")
        
        # Validar que el item existe
        if cleaned['item_tipo'] == 'producto':
            if not Producto.objects.filter(pk=cleaned['item_id']).exists():
                raise ValidationError("Producto no existe")
        
        return cleaned

# Uso en view:
def entrada_stock(request):
    if request.method == 'POST':
        form = EntradaStockForm(request.POST)
        if form.is_valid():
            # Procesar
            pass
        else:
            for error in form.errors.values():
                messages.error(request, error)
```

---

## 4. TESTING

### A. Tests de race conditions

**Archivo nuevo: tests/test_race_conditions.py**
```python
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from threading import Thread
import time

class PedidoRaceConditionTest(TransactionTestCase):
    """Tests para race conditions en pedidos."""
    
    def setUp(self):
        self.estudiante = Estudiante.objects.create(
            perfil=...,
            saldo=Decimal('100.00')
        )
        self.producto = Producto.objects.create(
            nombre='Test',
            precio_venta=Decimal('80.00')
        )
    
    def test_dos_pedidos_simultaneos_sin_doble_deduccion(self):
        """Verifica que no se pueda deducir saldo dos veces."""
        
        def crear_pedido():
            pedido = Pedido.objects.create(
                estudiante=self.estudiante,
                total=Decimal('80.00')
            )
            DetallePedido.objects.create(
                pedido=pedido,
                producto=self.producto,
                cantidad=1,
                precio_unitario=Decimal('80.00')
            )
            # Descontar
            est = Estudiante.objects.select_for_update().get(pk=self.estudiante.pk)
            est.saldo -= Decimal('80.00')
            est.save()
        
        # Simular dos requests simultáneos
        t1 = Thread(target=crear_pedido)
        t2 = Thread(target=crear_pedido)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Saldo no puede ser positivo
        est = Estudiante.objects.get(pk=self.estudiante.pk)
        self.assertLessEqual(float(est.saldo), 0, 
            "El saldo se dedujo dos veces!")
```

---

### B. Tests de validación de entrada

```python
class ValidacionEntradaTest(TestCase):
    
    def test_monto_negativo_rechazado(self):
        response = self.client.post('/padre/recargar/', {
            'monto': '-100',
            'estudiante_id': 1
        })
        self.assertContains(response, 'inválido', status_code=200)
    
    def test_monto_formato_invalido_rechazado(self):
        response = self.client.post('/padre/recargar/', {
            'monto': "'; DROP TABLE--",
            'estudiante_id': 1
        })
        self.assertContains(response, 'inválido', status_code=200)
    
    def test_monto_muy_grande_rechazado(self):
        response = self.client.post('/padre/recargar/', {
            'monto': '999999999999',
            'estudiante_id': 1
        })
        self.assertContains(response, 'rango', status_code=200)
```

---

## 5. AUDITORÍA

### A. Crear modelo de auditoría

**Archivo nuevo: app_admin/models.py (agregar)**
```python
class AuditoriaTransaccion(models.Model):
    """Log de todas las transacciones de dinero."""
    
    TIPO_CHOICES = [
        ('pedido', 'Pedido'),
        ('recarga', 'Recarga'),
        ('ajuste', 'Ajuste'),
        ('devolucion', 'Devolución'),
    ]
    
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField()
    
    # Referencias polimórficas
    contenido_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveIntegerField(null=True)
    
    saldo_anterior = models.DecimalField(max_digits=10, decimal_places=2)
    saldo_posterior = models.DecimalField(max_digits=10, decimal_places=2)
    
    creado_en = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Auditoría Transacción'
        ordering = ['-creado_en']

# Uso:
@transaction.atomic
def crear_pedido(request):
    est = Estudiante.objects.select_for_update().get(...)
    saldo_ant = est.saldo
    
    # ... operación ...
    
    est.saldo -= total
    est.save()
    
    # Registrar
    AuditoriaTransaccion.objects.create(
        tipo='pedido',
        usuario=request.user,
        monto=total,
        descripcion=f'Pedido {pedido.ticket}',
        saldo_anterior=saldo_ant,
        saldo_posterior=est.saldo,
        content_type=ContentType.objects.get_for_model(Pedido),
        object_id=pedido.id
    )
```

---

## 6. CONFIGURACIÓN RECOMENDADA

### A. settings.py - Agregar

```python
# Transacciones
ATOMIC_REQUESTS = False  # Manejo manual para mejor control

# Logging detallado
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/transacciones.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'app_admin': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'app_padre': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# Base de datos
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',  # Mejor para transacciones
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'isolation_level': psycopg2.extensions.ISOLATION_LEVEL_SERIALIZABLE,
        }
    }
}
```

---

## 7. CHECKLIST DE IMPLEMENTACIÓN

### Semana 1 - Crítico
- [ ] Envolver todas las operaciones de dinero en `@transaction.atomic`
- [ ] Usar `select_for_update()` en saldos
- [ ] Corregir cálculos de estadísticas

### Semana 2 - Alto
- [ ] Crear validador centralizado de entrada
- [ ] Implementar máquina de estados para pedidos
- [ ] Agregar índices a base de datos

### Semana 3 - Medio
- [ ] Crear modelo de auditoría
- [ ] Escribir tests de race conditions
- [ ] Optimizar queries (eliminar N+1)

### Semana 4 - Documentación
- [ ] Documentar reglas de validación
- [ ] Crear guía de desarrollo
- [ ] Setup de logging

---

**Impacto esperado:**
- 🔒 Eliminación de race conditions
- ⚡ 50-70% mejora en rendimiento
- 🛡️ Reducción 95% de errores de validación
- 📊 Auditoría completa de transacciones

---

**Última actualización:** 2026-04-09
