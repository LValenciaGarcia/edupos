"""
seed_completo.py — Seed completo para demo de Punto Asis.

Acciones:
  1. Corrige precios de ingredientes (lotes) y cantidades en recetas para
     que los productos tengan costos realistas (márgenes 30-60 %).
  2. Crea lotes de ingredientes con stock suficiente.
  3. Crea ventas distribuidas en los últimos 7 días (lunes-viernes semana actual).
  4. Crea producciones de elaborados.
  5. Crea pedidos de estudiante y docente.
  6. Registra movimientos de inventario e ingredientes.

Idempotente para ingredientes/recetas: actualiza, no duplica.
Las ventas SE ACUMULAN cada ejecución — ejecutar solo una vez para demo.
"""

import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import datetime

from app_admin.models import (
    Producto, Proveedor, Ingrediente, LoteIngrediente,
    RecetaIngrediente, ProduccionElaborado,
    Pedido, DetallePedido,
    MovimientoInventario, MovimientoIngrediente,
    Categoria,
)
from app_empleado.models import TurnoCaja, VentaEmpleado, DetalleVenta
from authentication.models import Empleado, Sede, Estudiante, Docente
from app_docente.models import PedidoDocente, DetallePedidoDocente


HOY = timezone.now().date()

# Días hábiles de esta semana (lunes a hoy, máximo 5 días)
def dias_semana():
    dias = []
    d = HOY
    while d.weekday() != 0:          # retroceder hasta el lunes
        d -= datetime.timedelta(days=1)
    lunes = d
    for i in range(5):               # lunes a viernes
        dia = lunes + datetime.timedelta(days=i)
        if dia <= HOY:
            dias.append(dia)
    return dias


# ─── Configuración de ingredientes: (nombre_exacto, precio_lote, unidades_compra,
#     contenido_por_unidad, unidad_base, unidad_compra_nombre, stock_inicial) ────

CORRECCIONES_INGREDIENTES = {
    # nombre exacto en BD → (precio_por_unidad_compra, unidades_compra, contenido_por_und, unidad_base, nombre_unidad_compra, stock_inicial)
    # Precios colombianos realistas 2025
    'Arroz':           (3200,  5, 1000, 'g',   'bolsa 1kg',    5000),  # $3200 bolsa 1kg = $3.2/g
    'Chocolate':       (5500,  3, 1,    'und',  'tableta',      20),    # $5500 tableta
    'Harina de trigo': (3000,  4, 1000, 'g',   'bolsa 1kg',    4000),  # $3000 bolsa 1kg = $3/g
    'Huevos':          (12000, 3, 30,   'und',  'cubeta 30',    150),   # $12000 cubeta 30 = $400/huevo
    'Papa':            (2500,  5, 1000, 'g',   'kilo',         5000),  # $2500/kg = $2.5/g
    'Papa amarilla':   (3000,  5, 1000, 'g',   'kilo',         5000),  # $3000/kg = $3/g
    'Queso mozzarella':(8000,  3, 500,  'g',   'bloque 500g',  3000),  # $8000 bloque 500g = $16/g
    'Salchicha':       (5500,  3, 8,    'und',  'paquete x8',   48),    # $5500 paquete x8 = $687/und
    'Arroz (g)':       (3200,  5, 1000, 'g',   'bolsa 1kg',    5000),  # alias si hay duplicado
}

# Recetas corregidas: producto → [(ingrediente_nombre, cantidad, unidad_base)]
# Costos target por producto (margen ~40-55 %):
# Dedo de queso $3500 → costo ~$1500
# Salchipapa $6000 → costo ~$2200
# Almuerzo sencillo $12000 → costo ~$4500
# Torta de chocolate $14000 → costo ~$5500

RECETAS_CORREGIDAS = {
    # Objetivo: margen 40-60 % sobre precio de venta
    'Dedo de queso': [           # venta $3500 → costo objetivo ~$1700
        ('Harina de trigo',  Decimal('80'),  'g'),   # 80g × $3/g = $240
        ('Queso mozzarella', Decimal('60'),  'g'),   # 60g × $16/g = $960
        ('Huevos',           Decimal('1'),   'und'), # 1 × $400 = $400
    ],                                               # total ≈ $1600 → margen 54%
    'Salchipapa': [              # venta $6000 → costo objetivo ~$2800
        ('Papa amarilla', Decimal('500'), 'g'),      # 500g × $3/g = $1500
        ('Salchicha',     Decimal('2'),   'und'),    # 2 × $688 = $1375
    ],                                               # total ≈ $2875 → margen 52%
    'Almuerzo sencillo': [       # venta $12000 → costo objetivo ~$5000
        ('Arroz',         Decimal('300'), 'g'),      # 300g × $3.2/g = $960
        ('Papa amarilla', Decimal('400'), 'g'),      # 400g × $3/g = $1200
        ('Huevos',        Decimal('2'),   'und'),    # 2 × $400 = $800
        ('Salchicha',     Decimal('3'),   'und'),    # 3 × $688 = $2063
    ],                                               # total ≈ $5023 → margen 58%
    'Torta de chocolate': [      # venta $14000 → costo objetivo ~$5850
        ('Harina de trigo',  Decimal('250'), 'g'),  # 250g × $3/g = $750
        ('Huevos',           Decimal('4'),   'und'),# 4 × $400 = $1600
        ('Chocolate',        Decimal('0.5'), 'und'),# 0.5 × $5500 = $2750
        ('Queso mozzarella', Decimal('50'),  'g'),  # 50g × $15/g = $750
    ],                                               # total ≈ $5850 → margen 58%
}


class Command(BaseCommand):
    help = 'Seed completo: corrige precios, crea ventas esta semana y estadísticas.'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write('[ ] Verificando datos base...')
            empleado, sede = self._get_empleado_sede()

            self.stdout.write('[ ] Corrigiendo ingredientes y lotes...')
            self._corregir_ingredientes()

            self.stdout.write('[ ] Corrigiendo recetas...')
            self._corregir_recetas()

            self.stdout.write('[ ] Creando producciones...')
            self._crear_producciones(empleado)

            self.stdout.write('[ ] Creando ventas de la semana...')
            self._crear_ventas_semana(empleado, sede)

            self.stdout.write('[ ] Creando pedidos estudiante y docente...')
            self._crear_pedidos_estudiante()
            self._crear_pedidos_docente()

        self.stdout.write(self.style.SUCCESS(
            'Seed completado. Hay datos de toda la semana con estadisticas y movimientos.'
        ))
        self._mostrar_resumen()

    # ─────────────────────────────────────────────────────────────────────────

    def _get_empleado_sede(self):
        empleado = Empleado.objects.first()
        sede = Sede.objects.first()
        if not empleado or not sede:
            raise Exception(
                'No hay empleados o sedes. Crea al menos uno de cada uno antes de correr este seed.'
            )
        return empleado, sede

    def _corregir_ingredientes(self):
        """
        Actualiza contenido_por_unidad, unidad_base, unidad_compra en cada
        ingrediente y crea (o actualiza) un lote con precio correcto.
        """
        proveedor = Proveedor.objects.first()
        fecha_venc = HOY + datetime.timedelta(days=90)

        for ing in Ingrediente.objects.filter(activo=True):
            cfg = CORRECCIONES_INGREDIENTES.get(ing.nombre)
            if not cfg:
                continue

            precio, unids_compra, contenido, unidad_base, nombre_und_compra, stock_ini = cfg

            # Actualizar el ingrediente
            ing.unidad_base = unidad_base
            ing.unidad_compra = nombre_und_compra
            ing.contenido_por_unidad = Decimal(str(contenido))
            ing.save(update_fields=['unidad_base', 'unidad_compra', 'contenido_por_unidad'])

            # Poner lotes vencidos/vacíos en 0
            ing.lotes.filter(
                cantidad_base__gt=0
            ).exclude(
                fecha_vencimiento__gte=HOY
            ).update(cantidad_base=Decimal('0'))

            # Crear lote fresco con precio correcto si el stock actual es insuficiente
            stock_actual = sum(
                float(l.cantidad_base) for l in ing.lotes.filter(
                    cantidad_base__gt=0, fecha_vencimiento__gte=HOY
                )
            )
            if stock_actual < stock_ini * 0.3:
                lote = LoteIngrediente.objects.create(
                    ingrediente=ing,
                    proveedor=proveedor,
                    unidades_compra=Decimal(str(unids_compra)),
                    precio_compra=Decimal(str(precio)),
                    cantidad_base=Decimal(str(stock_ini)),
                    cantidad_base_inicial=Decimal(str(stock_ini)),
                    fecha_vencimiento=fecha_venc,
                    nota='Lote seed_completo',
                )
                # Backdate ingreso al lunes de la semana
                lunes = HOY - datetime.timedelta(days=HOY.weekday())
                LoteIngrediente.objects.filter(pk=lote.pk).update(fecha_ingreso=lunes)

                # Registrar movimiento entrada
                MovimientoIngrediente.objects.create(
                    ingrediente=ing,
                    tipo='entrada',
                    cantidad=Decimal(str(stock_ini)),
                    nota='Entrada seed_completo',
                )

            costo_u = Decimal(str(precio)) / Decimal(str(contenido))
            self.stdout.write(f'   {ing.nombre}: costo/u={costo_u:.4f} {unidad_base}')

    def _corregir_recetas(self):
        """Reemplaza las recetas de los productos elaborados con valores correctos."""
        for nombre_prod, items in RECETAS_CORREGIDAS.items():
            try:
                prod = Producto.objects.get(nombre=nombre_prod, tipo='elaborado')
            except Producto.DoesNotExist:
                self.stdout.write(f'   [SKIP] Producto no encontrado: {nombre_prod}')
                continue

            # Borrar receta antigua
            prod.receta.all().delete()

            for nombre_ing, cantidad, _ in items:
                try:
                    # Buscar por nombre exacto; si hay dos con el mismo nombre tomar
                    # el que tenga la unidad_base correcta
                    ing = Ingrediente.objects.filter(nombre=nombre_ing, activo=True).first()
                    if not ing:
                        self.stdout.write(f'   [SKIP] Ingrediente no encontrado: {nombre_ing}')
                        continue
                    RecetaIngrediente.objects.create(
                        producto=prod,
                        ingrediente=ing,
                        cantidad=cantidad,
                    )
                except Exception as e:
                    self.stdout.write(f'   [ERROR] {nombre_ing}: {e}')

            costo = prod.costo_calculado
            margen = prod.margen
            self.stdout.write(
                f'   {prod.nombre}: costo={costo:.0f} | venta={prod.precio_venta:.0f} | margen={margen:.1f}%'
            )

    def _crear_producciones(self, empleado):
        """Crea producciones de elaborados con stock suficiente para las ventas."""
        user = empleado.perfil.user
        dias = dias_semana()

        elaborados = list(Producto.objects.filter(tipo='elaborado', disponible=True))
        if not elaborados:
            return

        for prod in elaborados:
            # Reponer stock
            if prod.stock < 80:
                entrada = 80 - prod.stock
                prod.stock = 80
                prod.save(update_fields=['stock'])
                MovimientoInventario.objects.create(
                    producto=prod,
                    tipo='entrada',
                    cantidad=Decimal(str(entrada)),
                    nota='Reposición seed_completo',
                )

            # Crear producción para cada día
            for i, dia in enumerate(dias):
                cantidad = random.randint(15, 25)
                hora = datetime.time(6, random.randint(0, 30))
                fecha_p = timezone.make_aware(datetime.datetime.combine(dia, hora))
                p = ProduccionElaborado.objects.create(
                    producto=prod,
                    cantidad_producida=cantidad,
                    responsable=user,
                    costo_total=Decimal(str(prod.costo_calculado)) * cantidad,
                    nota='Producción seed_completo',
                )
                ProduccionElaborado.objects.filter(pk=p.pk).update(fecha=fecha_p)

        # Reponer también productos simples
        for prod in Producto.objects.filter(tipo='simple', disponible=True):
            if prod.stock < 60:
                entrada = 80 - prod.stock
                prod.stock = 80
                prod.save(update_fields=['stock'])
                MovimientoInventario.objects.create(
                    producto=prod,
                    tipo='entrada',
                    cantidad=Decimal(str(entrada)),
                    nota='Reposición seed_completo',
                )

    def _crear_ventas_semana(self, empleado, sede):
        """Crea turnos y ventas para cada día hábil de la semana."""
        productos = list(Producto.objects.filter(disponible=True, stock__gt=0))
        if not productos:
            return

        tipos_pago = [
            'efectivo', 'efectivo', 'efectivo', 'efectivo',
            'cuenta_estudiante', 'cuenta_estudiante',
            'cuenta_docente',
        ]

        # Cantidad de ventas por día (lunes=más, viernes=menos)
        ventas_por_dia = [18, 22, 20, 19, 15]

        for i, dia in enumerate(dias_semana()):
            turno = self._crear_turno(empleado, sede, dia, es_hoy=(dia == HOY))
            n = ventas_por_dia[min(i, 4)]
            self._crear_ventas_dia(empleado, sede, turno, dia, productos, n)

            # Algunos movimientos de merma / ajuste para variedad
            if i % 2 == 0:
                ing = random.choice(list(Ingrediente.objects.filter(activo=True)))
                MovimientoIngrediente.objects.create(
                    ingrediente=ing,
                    tipo='merma',
                    cantidad=Decimal(str(random.randint(5, 30))),
                    nota='Merma por preparación',
                )

    def _crear_turno(self, empleado, sede, fecha, es_hoy=False):
        apertura = timezone.make_aware(
            datetime.datetime.combine(fecha, datetime.time(6, 30))
        )
        # Idempotente: reutilizar si ya existe
        turno = TurnoCaja.objects.filter(empleado=empleado, apertura__date=fecha).first()
        if turno:
            return turno

        if es_hoy:
            cierre = None
            estado = 'abierto'
            efectivo_final = None
        else:
            cierre = timezone.make_aware(
                datetime.datetime.combine(fecha, datetime.time(14, 0))
            )
            estado = 'cerrado'
            efectivo_final = Decimal(str(random.randint(80000, 180000)))

        turno = TurnoCaja.objects.create(
            empleado=empleado,
            sede=sede,
            estado=estado,
            apertura=apertura,
            cierre=cierre,
            efectivo_inicial=Decimal('50000'),
            efectivo_final=efectivo_final,
        )
        return turno

    def _crear_ventas_dia(self, empleado, sede, turno, fecha, productos, n):
        """Crea n ventas distribuidas a lo largo del día."""
        for _ in range(n):
            tipo_pago = random.choice([
                'efectivo', 'efectivo', 'efectivo',
                'cuenta_estudiante', 'cuenta_estudiante',
                'cuenta_docente',
            ])
            hora = datetime.time(
                random.randint(6, 13),
                random.randint(0, 59),
            )
            fecha_venta = timezone.make_aware(datetime.datetime.combine(fecha, hora))

            venta = VentaEmpleado.objects.create(
                empleado=empleado,
                sede=sede,
                turno=turno,
                tipo_pago=tipo_pago,
                total=Decimal('0'),
                nota='seed_completo',
            )
            VentaEmpleado.objects.filter(pk=venta.pk).update(fecha=fecha_venta)

            prods_disp = [p for p in productos if p.stock > 0]
            if not prods_disp:
                prods_disp = productos
            seleccion = random.sample(prods_disp, min(random.randint(1, 3), len(prods_disp)))

            total = Decimal('0')
            for prod in seleccion:
                cantidad = random.randint(1, 2)
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=prod,
                    cantidad=cantidad,
                    precio_unit=prod.precio_venta,
                )
                total += prod.precio_venta * cantidad
                new_stock = max(prod.stock - cantidad, 0)
                if new_stock != prod.stock:
                    prod.stock = new_stock
                    prod.save(update_fields=['stock'])
                    MovimientoInventario.objects.create(
                        producto=prod,
                        tipo='salida',
                        cantidad=Decimal(str(cantidad)),
                        nota='Venta seed_completo',
                    )

            venta.total = total
            venta.save(update_fields=['total'])

    def _crear_pedidos_estudiante(self):
        estudiantes = list(Estudiante.objects.all())
        if not estudiantes:
            return
        productos = list(Producto.objects.filter(disponible=True, stock__gt=0))
        if not productos:
            return

        dias = dias_semana()
        for i, dia in enumerate(dias):
            est = estudiantes[i % len(estudiantes)]
            for turno_idx in range(random.randint(1, 2)):
                hora = datetime.time(10 + turno_idx, random.randint(0, 59))
                fecha_p = timezone.make_aware(datetime.datetime.combine(dia, hora))

                pedido = Pedido(
                    estudiante=est,
                    estado='entregado',
                    total=Decimal('0'),
                    costo_total=Decimal('0'),
                    fecha_pedido=fecha_p,
                    fecha_entrega=fecha_p + datetime.timedelta(minutes=10),
                )
                pedido.save()
                Pedido.objects.filter(pk=pedido.pk).update(fecha_pedido=fecha_p)

                seleccion = random.sample(productos, min(random.randint(1, 3), len(productos)))
                for prod in seleccion:
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto=prod,
                        cantidad=1,
                        precio_unitario=prod.precio_venta,
                        costo_unitario=Decimal(str(prod.costo_calculado)),
                    )
                pedido.recalcular_totales()

    def _crear_pedidos_docente(self):
        docentes = list(Docente.objects.all())
        if not docentes:
            return
        productos = list(Producto.objects.filter(disponible=True, stock__gt=0))
        if not productos:
            return

        dias = dias_semana()
        for i, dia in enumerate(dias):
            doc = docentes[i % len(docentes)]
            hora = datetime.time(12, random.randint(0, 59))
            fecha_p = timezone.make_aware(datetime.datetime.combine(dia, hora))

            pedido = PedidoDocente.objects.create(
                docente=doc,
                estado='entregado',
                total=Decimal('0'),
                nota='seed_completo',
                fecha_pedido=fecha_p,
            )
            PedidoDocente.objects.filter(pk=pedido.pk).update(fecha_pedido=fecha_p)

            seleccion = random.sample(productos, min(random.randint(1, 2), len(productos)))
            total = Decimal('0')
            for prod in seleccion:
                DetallePedidoDocente.objects.create(
                    pedido=pedido,
                    producto=prod,
                    cantidad=1,
                    precio_unitario=prod.precio_venta,
                )
                total += prod.precio_venta
            pedido.total = total
            pedido.save(update_fields=['total'])

    def _mostrar_resumen(self):
        from app_admin.models import MovimientoIngrediente, MovimientoInventario
        self.stdout.write('=== RESUMEN ===')
        lunes = HOY - datetime.timedelta(days=HOY.weekday())
        self.stdout.write(f'Ventas esta semana: {VentaEmpleado.objects.filter(fecha__date__gte=lunes).count()}')
        self.stdout.write(f'Pedidos estudiante: {Pedido.objects.count()}')
        self.stdout.write(f'Movimientos ingredientes: {MovimientoIngrediente.objects.count()}')
        self.stdout.write(f'Movimientos inventario: {MovimientoInventario.objects.count()}')
        self.stdout.write('\nCostos/márgenes productos elaborados:')
        for p in Producto.objects.filter(tipo='elaborado'):
            self.stdout.write(
                f'  {p.nombre}: costo={p.costo_calculado:.0f} | venta={p.precio_venta:.0f} | margen={p.margen:.1f}%'
            )
