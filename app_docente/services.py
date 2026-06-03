"""
Capa de servicios para operaciones de pedidos del docente.
Encapsula validaciones de saldo y stock manteniendo las vistas limpias.
"""
from decimal import Decimal
import json

from django.db import transaction

from app_admin.models import Producto


class PedidoDocenteService:

    @staticmethod
    @transaction.atomic
    def confirmar_desde_carrito(docente, carrito_raw: str, nota: str, pedido_grupal=None):
        """
        Procesa un carrito JSON, valida saldo y stock, y crea el PedidoDocente.

        Args:
            docente: instancia Docente.
            carrito_raw: string JSON '[{"id": 1, "cantidad": 2}, ...]'
            nota: texto opcional del pedido.
            pedido_grupal: PedidoGrupal opcional (si el pedido se une a uno grupal).

        Returns:
            PedidoDocente creado.

        Raises:
            ValueError: si el carrito está vacío, no hay productos válidos,
                        falta stock o el saldo es insuficiente.
        """
        from .models import PedidoDocente, DetallePedidoDocente
        from authentication.models import Docente as DocenteModel

        try:
            carrito = json.loads(carrito_raw)
        except (json.JSONDecodeError, TypeError):
            raise ValueError('Carrito inválido.')

        items = []
        for item in carrito:
            try:
                producto = Producto.objects.select_for_update().get(pk=item['id'], disponible=True)
                cantidad = max(int(item.get('cantidad', 1)), 1)
                items.append((producto, cantidad))
            except (Producto.DoesNotExist, KeyError, ValueError):
                continue

        if not items:
            raise ValueError('No hay productos válidos en el carrito.')

        for producto, cantidad in items:
            if producto.tipo == 'simple' and producto.stock < cantidad:
                raise ValueError(
                    f'Stock insuficiente para "{producto.nombre}" '
                    f'(disponible: {producto.stock}, solicitado: {cantidad}).'
                )

        total = sum(Decimal(str(p.precio_venta)) * cant for p, cant in items)

        docente_locked = DocenteModel.objects.select_for_update().get(pk=docente.pk)

        if docente_locked.saldo < total:
            raise ValueError(
                f'Saldo insuficiente. Disponible: ${docente_locked.saldo:,.0f}, '
                f'requerido: ${total:,.0f}.'
            )

        pedido = PedidoDocente.objects.create(
            docente=docente_locked,
            nota=nota,
            total=total,
            pedido_grupal=pedido_grupal,
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

        docente_locked.saldo = Decimal(str(docente_locked.saldo)) - total
        docente_locked.save(update_fields=['saldo'])

        return pedido
