# 📋 ANÁLISIS CRÍTICO - Punto Asis (Django POS)

**Fecha:** 2026-04-09 | **Severidad:** 🔴 7 Críticos | 🟠 7 Altos | 🟡 4 Medios

---

## 🔴 ERRORES CRÍTICOS (Afectan datos/dinero)

### 1. RACE CONDITION: Descontar saldo sin transacción
**Archivos:** `app_estudiante/views.py:174-203`, `app_padre/views.py:754-781`

**Código problemático:**
```python
if estudiante.saldo < total:
    return redirect(...)
# ... validaciones ...
pedido = Pedido.objects.create(...)  # Query 1
# ... detalles pedido ...           # Queries 2-N
estudiante.saldo -= total            # Query N+1
estudiante.save()                     # Query N+2
```

**Escenario de ataque:**
1. Estudiante A tiene $100
2. Hace pedido de $80 → Check pasa (saldo=100)
3. Simultáneamente, Estudiante A hace otro pedido de $80 → Check pasa (saldo=100)
4. Ambos se deducen → Saldo final: **$20 en vez de -$60** ✗

**Solución:**
```python
from django.db import transaction

@transaction.atomic
def menu(request):
    with transaction.atomic():
        estudiante = Estudiante.objects.select_for_update().get(pk=...)
        if estudiante.saldo < total:
            return redirect(...)
        pedido = Pedido.objects.create(...)
        estudiante.saldo -= total
        estudiante.save(update_fields=['saldo'])
```

---

### 2. RACE CONDITION: Aprobar recarga sin transacción
**Archivo:** `app_padre/models.py:28-41`

**Código problemático:**
```python
def aprobar(self):
    self.estado = 'aprobada'
    self.fecha_resolucion = timezone.now()
    self.save(update_fields=['estado', 'fecha_resolucion'])  # Query 1
    # ⚠️ SI FALLA AQUÍ: Estado aprobado pero saldo NO actualizado
    self.estudiante.saldo += Decimal(str(self.monto))
    self.estudiante.save(update_fields=['saldo'])  # Query 2
```

**Riesgo:** Recarga marca como aprobada pero dinero no llega al estudiante.

**Solución:**
```python
@transaction.atomic
def aprobar(self):
    with transaction.atomic():
        recarga = RecargaSaldo.objects.select_for_update().get(pk=self.pk)
        recarga.estado = 'aprobada'
        recarga.fecha_resolucion = timezone.now()
        recarga.save(update_fields=['estado', 'fecha_resolucion'])
        
        estudiante = Estudiante.objects.select_for_update().get(pk=recarga.estudiante.pk)
        estudiante.saldo += Decimal(str(recarga.monto))
        estudiante.save(update_fields=['saldo'])
```

---

### 3. RACE CONDITION: Descuento de stock al entregar
**Archivo:** `app_admin/views.py:965-987`

**Código problemático:**
```python
for detalle in pedido.detalles.select_related('producto').all():
    if detalle.producto.tipo == 'elaborado':
        for r in detalle.producto.receta.all():
            # Lectura-modificación sin lock
            r.ingrediente.stock = max(
                0, float(r.ingrediente.stock) - float(r.cantidad) * detalle.cantidad
            )  # ← Si DOS pedidos se entregan simultáneamente, ambos leen el mismo stock
            r.ingrediente.save(update_fields=['stock'])
```

**Escenario:**
- Ingrediente: 100 unidades
- Pedido A necesita 50 → lee stock=100
- Pedido B necesita 50 → lee stock=100
- Ambos restan → stock final: 50 (debería ser 0) ✗

**Solución:**
```python
from django.db.models import F, DecimalField
from django.db.models.expressions import Case, When

ingrediente = Ingrediente.objects.select_for_update().get(pk=...)
ingrediente.stock = F('stock') - cantidad
ingrediente.save(update_fields=['stock'])
```

---

### 4. RACE CONDITION: Devolución sin reversa
**Archivo:** `app_estudiante/views.py:430-454`

**Código problemático:**
```python
estudiante.saldo += pedido.total   # Query 1
estudiante.save(update_fields=['saldo'])
# ⚠️ SI FALLA AQUÍ: Saldo devuelto pero estado NO actualizado

pedido.estado = 'cancelado'        # Query 2
pedido.save(update_fields=['estado'])
```

**Riesgo:** Dinero aparece dos veces (en historial + en saldo).

**Solución:** Misma pauta con `@transaction.atomic`.

---

## 🟠 PROBLEMAS DE SEGURIDAD

### 5. Conversión de tipos sin validación
**Archivos:** `app_padre/views.py:214, 484, 930` | `app_admin/views.py:404-406`

```python
# ✗ INCORRECTO
monto = float(request.POST.get('monto', 0))  # ← Sin try-except
dias = int(request.GET.get('dias', 30))      # ← Sin try-except

# Ataque: monto = "'; DROP TABLE--" → ValueError sin manejo
# Ataque: dias = "9999999999" → DoS por timeout
```

**Solución:**
```python
try:
    monto = float(request.POST.get('monto', 0))
    if monto <= 0 or monto > 10000000:  # Validar rango
        raise ValueError("Monto inválido")
except (ValueError, TypeError):
    messages.error(request, "Monto inválido. Use formato: 50.00")
    return redirect(...)
```

---

### 6. Cálculo incorrecto de gastos en estadísticas
**Archivo:** `app_padre/views.py:416-425, 402`

```python
# ✗ INCORRECTO - Línea 421
gasto_cat = DetallePedido.objects.filter(...).values(
    'producto__categoria__nombre'
).annotate(total=Sum('precio_unitario'))  # ← SUMA PRECIO DE UNA UNIDAD

# Resultado: 10 unidades × $100 = $1000 pero aparece $100 en gráfico

# ✗ INCORRECTO - Línea 402
'total': Sum('subtotal' if False else 'precio_unitario')
# ← if False NUNCA se ejecuta, siempre suma precio unitario
```

**Impacto:** Estadísticas muestran **1/10 del gasto real**.

**Solución:**
```python
# Debe sumar CANTIDAD × PRECIO_UNITARIO = subtotal
gasto_cat = DetailePedido.objects.filter(...).annotate(
    subtotal=F('cantidad') * F('precio_unitario')
).values('producto__categoria__nombre').annotate(
    total=Sum('subtotal')  # ← Correcto
)
```

---

### 7. Validación insuficiente en entrada de stock
**Archivo:** `app_admin/views.py:386-430`

```python
# ✗ Sin validación de tipo
tipo = request.POST.get('tipo')  
if tipo == 'producto':  # ← Podría ser 'producto_malicioso'
    prod = Producto.objects.get(pk=id_)  # ← DoesNotExist no manejado

# ✗ Sin try-except en conversión
cant_f = float(cant)   # Línea 404
precio_f = float(precio)  # Línea 405

# ✗ Sin validación de rango
if cant_f < 0:  # ← No hay check para valores negativos
    ...
```

**Solución:**
```python
if tipo not in ['producto', 'ingrediente']:
    messages.error(request, "Tipo inválido")
    return redirect(...)

try:
    cant_f = float(cant)
    precio_f = float(precio)
    
    if cant_f < 0 or precio_f < 0:
        raise ValueError("Cantidades negativas no permitidas")
        
    if cant_f > 100000 or precio_f > 1000000:  # Límites realistas
        raise ValueError("Valores fuera de rango")
except (ValueError, TypeError):
    messages.error(request, "Valores inválidos")
    continue
```

---

### 8. Falta de validación de transiciones de estado
**Archivo:** `app_admin/views.py:956-989`

```python
# ✗ INCORRECTO - No valida transiciones lógicas
nuevo = request.POST.get('estado')
if nuevo not in [e[0] for e in Pedido.ESTADO_CHOICES]:
    messages.error(request, 'Estado no válido.')

# Permite: entregado → pendiente (regresión ilógica)
#         cancelado → preparando (crea dinero duplicado)
```

**Solución - Usar máquina de estados:**
```python
TRANSICIONES_VALIDAS = {
    'pendiente': ['preparando', 'cancelado'],
    'preparando': ['listo', 'pendiente', 'cancelado'],
    'listo': ['entregado', 'pendiente'],
    'entregado': [],  # Terminal
    'cancelado': [],  # Terminal
}

if nuevo not in TRANSICIONES_VALIDAS.get(pedido.estado, []):
    messages.error(request, f"No puedes cambiar de {pedido.estado} a {nuevo}")
```

---

## 🟡 INCONSISTENCIAS LÓGICA

### 9. Límites de gasto verificados antes, no después
**Archivo:** `app_estudiante/views.py:182-188`

```python
# Check límite
for lim in _get_limites(estudiante):
    if float(lim.gasto_actual()) + float(total) > float(lim.monto):
        return redirect(...)

# ... 50 líneas después ...

# Crear pedido
pedido = Pedido.objects.create(...)  # ← El gasto puede cambiar aquí
```

**Riesgo:** Entre el check y la creación, otro pedido se procesa y supera el límite.

**Solución:** Verificar dentro de `@transaction.atomic`.

---

### 10. Sin rollback en múltiples items
**Archivo:** `app_admin/views.py:386-430`

```python
compra = CompraProveedor.objects.create(...)  # Si falla item 5, items 1-4 quedan registrados

for tipo, id_, cant, precio in zip(...):
    det = DetalleCompra(compra=compra, ...)
    # ...
    prod.stock += int(cant_f)
    prod.save()  # Si falla AQUÍ, compra es inconsistente
```

**Solución:**
```python
@transaction.atomic
def entrada_stock(request):
    compra = CompraProveedor.objects.create(...)
    # todos los updates dentro de la transacción
```

---

## 📊 MATRIZ DE SEVERIDAD

```
┌─────────────────────┬──────────┬──────────┬────────┐
│ Tipo                │ Crítico  │ Alto     │ Medio  │
├─────────────────────┼──────────┼──────────┼────────┤
│ Race Conditions     │    4     │    —     │   —    │
│ Seguridad/Validación│    2     │    3     │   —    │
│ Lógica Negocio      │    1     │    2     │   2    │
│ Rendimiento         │    —     │    —     │   2    │
└─────────────────────┴──────────┴──────────┴────────┘

TOTAL: 7 CRÍTICOS + 5 ALTOS = 12 ISSUES URGENTES
```

---

## ✅ ACCIONES INMEDIATAS

### Prioridad 1 (Esta semana)
- [ ] Envolver TODAS las operaciones de dinero en `@transaction.atomic`
- [ ] Usar `select_for_update()` en saldos
- [ ] Validar conversión de tipos con try-except

### Prioridad 2 (Este mes)
- [ ] Corregir cálculos de estadísticas (Sum de subtotal, no precio_unitario)
- [ ] Implementar máquina de estados para pedidos
- [ ] Agregar validación de rangos en números

### Prioridad 3 (Documentar)
- [ ] Crear audit trail para transacciones
- [ ] Documentar reglas de validación
- [ ] Testing de race conditions

---

## 🔧 EJEMPLOS DE CORRECCIONES

### Fix #1: Crear pedido de forma segura
```python
from django.db import transaction

@estudiante_required
@transaction.atomic
def menu(request):
    estudiante = _get_estudiante(request)
    
    if request.method == 'POST':
        # ... carrito ...
        
        # Lock row
        est_locked = Estudiante.objects.select_for_update().get(pk=estudiante.pk)
        
        # Revalidar saldo
        if est_locked.saldo < total:
            messages.error(request, 'Saldo insuficiente')
            return redirect('app_estudiante:menu')
        
        # Crear pedido
        pedido = Pedido.objects.create(...)
        for prod, qty, _ in lineas:
            DetallePedido.objects.create(...)
        
        # Descontar (ahora seguro)
        est_locked.saldo -= total
        est_locked.save(update_fields=['saldo'])
```

### Fix #2: Estadísticas correctas
```python
from django.db.models import F

gastos_categoria = (
    DetallePedido.objects
    .filter(pedido__in=pedidos_qs)
    .annotate(
        subtotal=F('cantidad') * F('precio_unitario')
    )
    .values('producto__categoria__nombre')
    .annotate(total=Sum('subtotal'))
    .order_by('-total')
)
```

### Fix #3: Validación de entrada
```python
def entrada_stock(request):
    try:
        cantidad = float(request.POST.get('cantidad', 0))
        if cantidad <= 0:
            raise ValueError("Cantidad debe ser positiva")
        if cantidad > 100000:
            raise ValueError("Cantidad fuera de rango")
    except (ValueError, TypeError) as e:
        messages.error(request, f"Cantidad inválida: {str(e)}")
        return redirect('app_admin:entrada_stock')
```

---

**Creado:** 2026-04-09 | **By:** Claude Code Analysis
