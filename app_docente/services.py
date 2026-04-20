"""
Capa de servicios para operaciones financieras del docente.
Encapsula la lógica de negocio de pedidos y fiado, manteniendo las vistas limpias.
"""
from decimal import Decimal
import json

from django.db import transaction

from app_admin.models import Producto


class PedidoDocenteService:

    @staticmethod
    @transaction.atomic
    def confirmar_desde_carrito(docente, carrito_raw: str, nota: str, tipo_pago: str):
        """
        Procesa un carrito JSON, valida balance/fiado y crea el PedidoDocente.

        Args:
            docente: instancia Docente (con select_for_update aplicado en la vista).
            carrito_raw: string JSON '[{"id": 1, "cantidad": 2}, ...]'
            nota: texto opcional del pedido
            tipo_pago: 'saldo' | 'fiado'

        Returns:
            PedidoDocente creado.

        Raises:
            ValueError: si el carrito está vacío, el saldo es insuficiente o el fiado excede el límite.
        """
        from .models import PedidoDocente, DetallePedidoDocente
        from authentication.models import Docente as DocenteModel

        try:
            carrito = json.loads(carrito_raw)
        except (json.JSONDecodeError, TypeError):
            raise ValueError('Carrito inválido.')

        # Construir ítems validados
        items = []
        for item in carrito:
            try:
                producto = Producto.objects.get(pk=item['id'], disponible=True)
                cantidad = max(int(item.get('cantidad', 1)), 1)
                items.append((producto, cantidad))
            except (Producto.DoesNotExist, KeyError, ValueError):
                continue

        if not items:
            raise ValueError('No hay productos válidos en el carrito.')

        total = sum(p.precio_venta * cant for p, cant in items)

        # Re-bloquear el docente dentro de la transacción para evitar race conditions
        docente_locked = DocenteModel.objects.select_for_update().get(pk=docente.pk)

        if tipo_pago == 'saldo':
            if docente_locked.saldo < total:
                raise ValueError(f'Saldo insuficiente. Disponible: ${docente_locked.saldo:,.0f}, requerido: ${total:,.0f}.')
        else:
            if docente_locked.credito_disponible < total:
                raise ValueError(
                    f'Límite de fiado excedido. Crédito disponible: ${docente_locked.credito_disponible:,.0f}, '
                    f'requerido: ${total:,.0f}.'
                )

        pedido = PedidoDocente.objects.create(
            docente=docente_locked,
            nota=nota,
            tipo_pago=tipo_pago,
            total=total,
        )
        DetallePedidoDocente.objects.bulk_create([
            DetallePedidoDocente(
                pedido=pedido,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio_venta,
            )
            for producto, cantidad in items
        ])

        if tipo_pago == 'saldo':
            docente_locked.saldo = Decimal(str(docente_locked.saldo)) - total
        else:
            docente_locked.deuda_fiado = Decimal(str(docente_locked.deuda_fiado)) + total
        docente_locked.save(update_fields=['saldo', 'deuda_fiado'])

        # Registrar movimiento de fiado
        if tipo_pago == 'fiado':
            from .models import MovimientoFiado
            MovimientoFiado.objects.create(
                docente=docente_locked,
                tipo='cargo',
                monto=total,
                saldo_post=docente_locked.deuda_fiado,
                referencia=pedido,
                nota=f'Pedido {pedido.ticket}',
            )

        return pedido

    @staticmethod
    @transaction.atomic
    def abonar_fiado(docente, monto: Decimal, nota: str = ''):
        """Registra un abono al fiado del docente."""
        from .models import MovimientoFiado
        from authentication.models import Docente as DocenteModel

        docente_locked = DocenteModel.objects.select_for_update().get(pk=docente.pk)
        if monto <= 0:
            raise ValueError('El monto del abono debe ser mayor a cero.')
        if monto > docente_locked.deuda_fiado:
            raise ValueError('El abono supera la deuda actual.')

        docente_locked.deuda_fiado = Decimal(str(docente_locked.deuda_fiado)) - monto
        docente_locked.save(update_fields=['deuda_fiado'])

        MovimientoFiado.objects.create(
            docente=docente_locked,
            tipo='abono',
            monto=monto,
            saldo_post=docente_locked.deuda_fiado,
            nota=nota or 'Abono manual',
        )
        return docente_locked
