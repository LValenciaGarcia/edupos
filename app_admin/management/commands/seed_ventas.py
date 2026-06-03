"""
seed_ventas.py  —  Inserta ventas, producciones y lotes de demostración.

Genera datos para HOY y AYER:
  • 2 TurnosCaja (uno por día)
  • ~8–10 VentaEmpleado con varios DetalleVenta por turno
  • 3–4 ProduccionElaborado backdateadas
  • 2 Pedido de estudiante (estado entregado)
  • 2 LoteIngrediente nuevos para reponer stock

Seguridad:
  - Idempotente: si ya existen turnos del día no crea duplicados.
  - No toca datos existentes de usuarios, ingredientes ni recetas.
  - Ajusta stock de productos antes de crear ventas para no quedar negativo.
"""

import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import datetime

from app_admin.models import (
    Producto, Proveedor, Ingrediente, LoteIngrediente,
    ProduccionElaborado, Pedido, DetallePedido,
)
from app_empleado.models import TurnoCaja, VentaEmpleado, DetalleVenta
from authentication.models import Empleado, Sede, Estudiante


HOY = timezone.now().date()
AYER = HOY - datetime.timedelta(days=1)


class Command(BaseCommand):
    help = 'Inserta ventas, producciones y lotes de demo para hoy y ayer.'

    def handle(self, *args, **options):
        with transaction.atomic():
            empleado, sede = self._get_empleado_sede()
            self._reponer_stock_productos()
            self._reponer_lotes_ingredientes()
            self._crear_producciones(empleado)
            turno_ayer = self._crear_turno(empleado, sede, AYER)
            turno_hoy  = self._crear_turno(empleado, sede, HOY)
            self._crear_ventas(empleado, sede, turno_ayer, AYER, n=9)
            self._crear_ventas(empleado, sede, turno_hoy,  HOY,  n=10)
            self._crear_pedidos_estudiante()
        self.stdout.write(self.style.SUCCESS('Seed completado. Revisa el dashboard de ventas.'))

    # ─────────────────────────────────────────────────────────────────────────

    def _get_empleado_sede(self):
        empleado = Empleado.objects.first()
        sede     = Sede.objects.first()
        if not empleado or not sede:
            raise Exception('No hay empleados o sedes en la BD. Crea uno antes de ejecutar este comando.')
        return empleado, sede

    def _reponer_stock_productos(self):
        """Garantiza stock suficiente en todos los productos para las ventas simuladas."""
        for p in Producto.objects.filter(disponible=True):
            if p.stock < 30:
                p.stock = 50
                p.save(update_fields=['stock'])

    def _reponer_lotes_ingredientes(self):
        """Añade 2 lotes nuevos de ingredientes clave para que producciones funcionen."""
        proveedor = Proveedor.objects.first()
        if not proveedor:
            return

        ingredientes_reponer = Ingrediente.objects.filter(activo=True)[:4]
        fecha_venc = HOY + datetime.timedelta(days=60)

        for ing in ingredientes_reponer:
            # Solo crea si el stock está bajo
            if ing.stock_real < 50:
                lote = LoteIngrediente.objects.create(
                    ingrediente=ing,
                    proveedor=proveedor,
                    unidades_compra=Decimal('10'),
                    precio_compra=Decimal('8000'),
                    cantidad_base=Decimal('200'),
                    cantidad_base_inicial=Decimal('200'),
                    fecha_vencimiento=fecha_venc,
                    nota='Lote de demo — seed_ventas',
                )
                # Backdate al día anterior
                LoteIngrediente.objects.filter(pk=lote.pk).update(
                    fecha_ingreso=AYER
                )

    def _crear_producciones(self, empleado):
        """Crea producciones de productos elaborados backdateadas."""
        productos_elaborados = list(Producto.objects.filter(tipo='elaborado', disponible=True))
        if not productos_elaborados:
            return

        producciones = [
            # (producto_idx, cantidad, dias_atras)
            (0, 20, 1),  # ayer
            (0, 15, 0),  # hoy
            (1, 10, 1),  # ayer
            (1, 12, 0),  # hoy
        ]

        user = empleado.perfil.user
        for idx, cantidad, dias_atras in producciones:
            if idx >= len(productos_elaborados):
                idx = 0
            prod = productos_elaborados[idx]
            p = ProduccionElaborado.objects.create(
                producto=prod,
                cantidad_producida=cantidad,
                responsable=user,
                costo_total=Decimal(str(prod.costo_calculado)) * cantidad,
                nota='Producción demo — seed_ventas',
            )
            fecha_prod = timezone.now() - datetime.timedelta(days=dias_atras)
            ProduccionElaborado.objects.filter(pk=p.pk).update(fecha=fecha_prod)

    def _crear_turno(self, empleado, sede, fecha):
        """Crea o reutiliza un TurnoCaja para la fecha dada."""
        apertura = timezone.make_aware(
            datetime.datetime.combine(fecha, datetime.time(6, 30))
        )
        # Reutilizar turno existente del día para idempotencia
        turno = TurnoCaja.objects.filter(
            empleado=empleado,
            apertura__date=fecha,
        ).first()
        if turno:
            return turno

        cierre = None
        estado = 'abierto'
        if fecha == AYER:
            cierre = timezone.make_aware(
                datetime.datetime.combine(fecha, datetime.time(14, 0))
            )
            estado = 'cerrado'

        turno = TurnoCaja.objects.create(
            empleado=empleado,
            sede=sede,
            estado=estado,
            apertura=apertura,
            cierre=cierre,
            efectivo_inicial=Decimal('50000'),
            efectivo_final=Decimal('350000') if fecha == AYER else None,
        )
        return turno

    def _crear_ventas(self, empleado, sede, turno, fecha, n=10):
        """Crea n ventas con 1-3 productos cada una distribuidas a lo largo del día."""
        productos = list(Producto.objects.filter(disponible=True, stock__gt=0))
        if not productos:
            return

        tipos_pago = ['efectivo', 'efectivo', 'efectivo', 'cuenta_estudiante', 'cuenta_docente']

        for i in range(n):
            tipo_pago = random.choice(tipos_pago)

            # Hora aleatoria entre 6:30 y 13:30
            hora = datetime.time(
                random.randint(6, 13),
                random.randint(0, 59),
            )
            fecha_venta = timezone.make_aware(
                datetime.datetime.combine(fecha, hora)
            )

            venta = VentaEmpleado.objects.create(
                empleado=empleado,
                sede=sede,
                turno=turno,
                tipo_pago=tipo_pago,
                total=Decimal('0'),
                nota='Demo seed_ventas',
            )
            # Backdate
            VentaEmpleado.objects.filter(pk=venta.pk).update(fecha=fecha_venta)

            # 1–3 productos distintos por venta
            seleccion = random.sample(productos, min(random.randint(1, 3), len(productos)))
            total = Decimal('0')
            for prod in seleccion:
                cantidad = random.randint(1, 3)
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=prod,
                    cantidad=cantidad,
                    precio_unit=prod.precio_venta,
                )
                total += prod.precio_venta * cantidad
                # Descontar stock
                prod.stock = max(prod.stock - cantidad, 0)
                prod.save(update_fields=['stock'])

            venta.total = total
            venta.save(update_fields=['total'])

    def _crear_pedidos_estudiante(self):
        """Crea pedidos de estudiante para hoy y ayer."""
        estudiantes = list(Estudiante.objects.all())
        if not estudiantes:
            return
        productos = list(Producto.objects.filter(disponible=True, stock__gt=0))
        if not productos:
            return

        for i, dia in enumerate([AYER, HOY]):
            estudiante = estudiantes[i % len(estudiantes)]
            hora = datetime.time(10, 30 + i * 15)
            fecha_p = timezone.make_aware(datetime.datetime.combine(dia, hora))

            pedido = Pedido(
                estudiante=estudiante,
                estado='entregado',
                total=Decimal('0'),
                costo_total=Decimal('0'),
                fecha_pedido=fecha_p,
                fecha_entrega=fecha_p + datetime.timedelta(minutes=15),
            )
            pedido.save()
            Pedido.objects.filter(pk=pedido.pk).update(fecha_pedido=fecha_p)

            seleccion = random.sample(productos, min(2, len(productos)))
            for prod in seleccion:
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto=prod,
                    cantidad=1,
                    precio_unitario=prod.precio_venta,
                    costo_unitario=Decimal(str(prod.costo_calculado)),
                )
            pedido.recalcular_totales()
