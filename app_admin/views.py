from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from datetime import date, timedelta
import json

from authentication.models import Perfil, Estudiante, Padre
from .models import (
    Producto, Categoria, Ingrediente, RecetaIngrediente,
    Proveedor, CompraProveedor, DetalleCompra,
    Pedido, DetallePedido,
    MovimientoInventario, MovimientoIngrediente,
    PerfilAdmin,
)


# ══════════════════════════════════════════════════════════════════════════════
# DECORADOR
# ══════════════════════════════════════════════════════════════════════════════

def admin_required(view_func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        try:
            if request.user.perfil.rol != 'admin':
                messages.error(request, 'No tienes permisos de administrador.')
                return redirect('authentication:login')
        except Perfil.DoesNotExist:
            return redirect('authentication:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_alertas():
    """Devuelve conteo de alertas activas para el topbar."""
    stock_prod = Producto.objects.filter(tipo='simple', stock__lte=F('stock_minimo')).count()
    stock_ing  = Ingrediente.objects.filter(activo=True, stock__lte=F('stock_minimo')).count()
    vencidos   = Ingrediente.objects.filter(
        activo=True, fecha_vencimiento__lt=date.today()
    ).count()
    vence_pronto = Ingrediente.objects.filter(
        activo=True,
        fecha_vencimiento__gte=date.today(),
        fecha_vencimiento__lte=date.today() + timedelta(days=7)
    ).count()
    pedidos_pend = Pedido.objects.filter(
        estado__in=['pendiente', 'preparando'],
        fecha_pedido__date=date.today()
    ).count()
    total = stock_prod + stock_ing + vencidos + vence_pronto + pedidos_pend
    return {
        'total': total,
        'stock_prod': stock_prod,
        'stock_ing': stock_ing,
        'vencidos': vencidos,
        'vence_pronto': vence_pronto,
        'pedidos_pend': pedidos_pend,
    }


def _ctx(extra=None):
    """Contexto base con alertas para todas las vistas admin."""
    ctx = {'alertas': _get_alertas()}
    if extra:
        ctx.update(extra)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def dashboard(request):
    hoy = date.today()
    pedidos_hoy  = Pedido.objects.filter(fecha_pedido__date=hoy)
    ventas_hoy   = pedidos_hoy.aggregate(t=Sum('total'))['t'] or 0
    ganancia_hoy = float(ventas_hoy) - float(
        pedidos_hoy.aggregate(t=Sum('costo_total'))['t'] or 0
    )
    pendientes  = pedidos_hoy.filter(estado__in=['pendiente', 'preparando']).count()
    entregados  = pedidos_hoy.filter(estado='entregado').count()

    # Stock crítico: productos E ingredientes juntos
    prods_criticos = Producto.objects.filter(
        tipo='simple', stock__lte=F('stock_minimo')
    ).select_related('proveedor').order_by('stock')[:8]

    ings_criticos = Ingrediente.objects.filter(
        activo=True, stock__lte=F('stock_minimo')
    ).select_related('proveedor').order_by('stock')[:8]

    ultimos_pedidos = Pedido.objects.select_related(
        'estudiante__perfil__user'
    ).order_by('-fecha_pedido')[:8]

    context = _ctx({
        'ventas_hoy':      ventas_hoy,
        'ganancia_hoy':    ganancia_hoy,
        'pendientes':      pendientes,
        'entregados':      entregados,
        'total_pedidos':   pedidos_hoy.count(),
        'prods_criticos':  prods_criticos,
        'ings_criticos':   ings_criticos,
        'ultimos_pedidos': ultimos_pedidos,
        'fecha_hoy':       hoy,
    })
    return render(request, 'app_admin/dashboard.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# PRODUCTOS
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def productos(request):
    qs = Producto.objects.select_related('categoria', 'proveedor').prefetch_related('receta__ingrediente').all()
    cat_f  = request.GET.get('categoria', '')
    tipo_f = request.GET.get('tipo', '')
    disp_f = request.GET.get('disponible', '')
    q      = request.GET.get('q', '').strip()

    if cat_f:  qs = qs.filter(categoria__nombre=cat_f)
    if tipo_f: qs = qs.filter(tipo=tipo_f)
    if disp_f == '1': qs = qs.filter(disponible=True)
    if disp_f == '0': qs = qs.filter(disponible=False)
    if q: qs = qs.filter(nombre__icontains=q)

    lista = list(qs)
    kpi = {
        'total':      len(lista),
        'sin_stock':  sum(1 for p in lista if p.sin_stock),
        'stock_bajo': sum(1 for p in lista if p.stock_bajo and not p.sin_stock),
        'elaborados': sum(1 for p in lista if p.tipo == 'elaborado'),
    }
    movimientos = MovimientoInventario.objects.select_related('producto').order_by('-fecha')[:20]

    return render(request, 'app_admin/productos.html', _ctx({
        'productos':   qs,
        'categorias':  Categoria.objects.filter(activa=True),
        'cat_f': cat_f, 'tipo_f': tipo_f, 'disp_f': disp_f, 'q': q,
        'kpi':         kpi,
        'movimientos': movimientos,
    }))


@admin_required
def producto_nuevo(request):
    categorias   = Categoria.objects.filter(activa=True)
    proveedores  = Proveedor.objects.filter(activo=True)
    ingredientes = Ingrediente.objects.filter(activo=True)

    if request.method == 'POST':
        tipo     = request.POST.get('tipo', 'simple')
        nombre   = request.POST.get('nombre', '').strip()
        desc     = request.POST.get('descripcion', '').strip()
        precio_v = request.POST.get('precio_venta')
        precio_c = request.POST.get('precio_costo') or None
        cat_id   = request.POST.get('categoria')
        prov_id  = request.POST.get('proveedor') or None
        stock    = request.POST.get('stock', 0)
        stock_min = request.POST.get('stock_minimo', 5)
        disponible = request.POST.get('disponible') == 'on'
        imagen   = request.FILES.get('imagen')

        errores = []
        if not nombre or not precio_v or not cat_id:
            errores.append('Nombre, precio de venta y categoría son obligatorios.')
        if tipo == 'simple' and not prov_id:
            errores.append('Los productos simples requieren un proveedor.')

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            p = Producto.objects.create(
                tipo=tipo, nombre=nombre, descripcion=desc,
                precio_venta=precio_v,
                precio_costo=precio_c if tipo == 'simple' else None,
                categoria_id=cat_id,
                proveedor_id=prov_id if tipo == 'simple' else None,
                stock=stock if tipo == 'simple' else 0,
                stock_minimo=stock_min,
                disponible=disponible, imagen=imagen,
            )
            if tipo == 'elaborado':
                for i_id, i_cant in zip(
                    request.POST.getlist('ingrediente_id'),
                    request.POST.getlist('ingrediente_cant')
                ):
                    if i_id and i_cant:
                        RecetaIngrediente.objects.create(producto=p, ingrediente_id=i_id, cantidad=i_cant)
            messages.success(request, f'Producto "{p.nombre}" creado.')
            return redirect('app_admin:productos')

    return render(request, 'app_admin/producto_form.html', _ctx({
        'categorias': categorias, 'proveedores': proveedores,
        'ingredientes': ingredientes, 'accion': 'Nuevo producto',
    }))


@admin_required
def producto_editar(request, pk):
    producto     = get_object_or_404(Producto, pk=pk)
    categorias   = Categoria.objects.filter(activa=True)
    proveedores  = Proveedor.objects.filter(activo=True)
    ingredientes = Ingrediente.objects.filter(activo=True)
    receta       = producto.receta.select_related('ingrediente').all()

    if request.method == 'POST':
        tipo_orig = producto.tipo
        producto.nombre       = request.POST.get('nombre', producto.nombre).strip()
        producto.descripcion  = request.POST.get('descripcion', '').strip()
        producto.precio_venta = request.POST.get('precio_venta', producto.precio_venta)
        producto.disponible   = request.POST.get('disponible') == 'on'
        cat_id = request.POST.get('categoria')
        if cat_id:
            producto.categoria_id = cat_id

        if producto.tipo == 'simple':
            prov_id = request.POST.get('proveedor') or None
            if not prov_id:
                messages.error(request, 'Los productos simples requieren un proveedor.')
                return render(request, 'app_admin/producto_form.html', _ctx({
                    'producto': producto, 'categorias': categorias,
                    'proveedores': proveedores, 'ingredientes': ingredientes,
                    'receta': receta, 'accion': 'Editar producto',
                }))
            producto.precio_costo = request.POST.get('precio_costo') or None
            producto.proveedor_id = prov_id
            producto.stock        = request.POST.get('stock', producto.stock)
            producto.stock_minimo = request.POST.get('stock_minimo', producto.stock_minimo)

        if request.FILES.get('imagen'):
            producto.imagen = request.FILES['imagen']
        producto.save()

        if producto.tipo == 'elaborado':
            producto.receta.all().delete()
            for i_id, i_cant in zip(
                request.POST.getlist('ingrediente_id'),
                request.POST.getlist('ingrediente_cant')
            ):
                if i_id and i_cant:
                    RecetaIngrediente.objects.create(producto=producto, ingrediente_id=i_id, cantidad=i_cant)

        messages.success(request, f'Producto "{producto.nombre}" actualizado.')
        return redirect('app_admin:productos')

    return render(request, 'app_admin/producto_form.html', _ctx({
        'producto': producto, 'categorias': categorias,
        'proveedores': proveedores, 'ingredientes': ingredientes,
        'receta': receta, 'accion': 'Editar producto',
    }))


@admin_required
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f'Producto "{nombre}" eliminado.')
    return redirect('app_admin:productos')


@admin_required
def producto_toggle(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.disponible = not producto.disponible
        producto.save(update_fields=['disponible'])
    return redirect('app_admin:productos')


# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def inventario(request):
    qs = Producto.objects.select_related('categoria', 'proveedor').all()
    cat_f  = request.GET.get('categoria', '')
    tipo_f = request.GET.get('tipo', '')
    q      = request.GET.get('q', '').strip()
    if cat_f:  qs = qs.filter(categoria__nombre=cat_f)
    if tipo_f: qs = qs.filter(tipo=tipo_f)
    if q:      qs = qs.filter(Q(nombre__icontains=q) | Q(proveedor__nombre__icontains=q))

    ings = Ingrediente.objects.select_related('proveedor').filter(activo=True)
    if q: ings = ings.filter(Q(nombre__icontains=q) | Q(proveedor__nombre__icontains=q))

    movimientos = MovimientoInventario.objects.select_related(
        'producto', 'compra__proveedor'
    ).order_by('-fecha')[:30]

    movimientos_ings = MovimientoIngrediente.objects.select_related(
        'ingrediente', 'compra__proveedor'
    ).order_by('-fecha')[:30]

    return render(request, 'app_admin/inventario.html', _ctx({
        'productos':        qs,
        'ingredientes':     ings,
        'movimientos':      movimientos,
        'movimientos_ings': movimientos_ings,
        'categorias':       Categoria.objects.filter(activa=True),
        'cat_f': cat_f, 'tipo_f': tipo_f, 'q': q,
    }))


@admin_required
def inventario_ajuste(request, pk):
    """Ajuste/salida/merma — las entradas van por entrada_stock."""
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        tipo     = request.POST.get('tipo', 'ajuste')
        cantidad = int(request.POST.get('cantidad', 0))
        nota     = request.POST.get('nota', '').strip()

        if tipo == 'salida':
            producto.stock = max(0, producto.stock - cantidad)
        elif tipo == 'ajuste':
            producto.stock = cantidad
        elif tipo == 'merma':
            producto.stock = max(0, producto.stock - cantidad)

        producto.save(update_fields=['stock'])
        MovimientoInventario.objects.create(
            producto=producto, tipo=tipo, cantidad=cantidad, nota=nota
        )
        messages.success(request, f'Inventario de "{producto.nombre}" actualizado.')
    return redirect('app_admin:inventario')


@admin_required
def inventario_historial(request, pk):
    producto    = get_object_or_404(Producto, pk=pk)
    movimientos = producto.movimientos.select_related('compra__proveedor').order_by('-fecha')
    return render(request, 'app_admin/inventario_historial.html', _ctx({
        'producto':    producto,
        'movimientos': movimientos,
    }))


# ──────────────────────────────────────────────────────────────────────────────
# ENTRADA UNIFICADA DE STOCK
# ──────────────────────────────────────────────────────────────────────────────

@admin_required
def entrada_stock(request, pk=None):
    """
    Formulario único de entrada de stock.
    Siempre crea una CompraProveedor y vincula el movimiento.
    Si se llama con pk, preselecciona ese producto.
    Si viene ?ing=<pk>, preselecciona ese ingrediente.
    """
    proveedores  = Proveedor.objects.filter(activo=True)
    productos    = Producto.objects.filter(tipo='simple').select_related('proveedor')
    ingredientes = Ingrediente.objects.filter(activo=True).select_related('proveedor')
    producto_sel    = get_object_or_404(Producto, pk=pk) if pk else None
    ing_pk          = request.GET.get('ing', '').strip()
    ingrediente_sel = get_object_or_404(Ingrediente, pk=ing_pk) if ing_pk else None

    if request.method == 'POST':
        prov_id  = request.POST.get('proveedor')
        fecha    = request.POST.get('fecha', str(date.today()))
        nota     = request.POST.get('nota', '').strip()

        if not prov_id:
            messages.error(request, 'Debes seleccionar un proveedor.')
            return render(request, 'app_admin/entrada_stock.html', _ctx({
                'proveedores': proveedores, 'productos': productos,
                'ingredientes': ingredientes, 'producto_sel': producto_sel,
                'ingrediente_sel': ingrediente_sel,
            }))

        # Crear compra
        compra = CompraProveedor.objects.create(
            proveedor_id=prov_id, fecha=fecha, nota=nota
        )

        item_tipos  = request.POST.getlist('item_tipo')
        item_ids    = request.POST.getlist('item_id')
        item_cants  = request.POST.getlist('item_cantidad')
        item_precios = request.POST.getlist('item_precio')

        total = 0
        for tipo, id_, cant, precio in zip(item_tipos, item_ids, item_cants, item_precios):
            if not (id_ and cant and precio):
                continue
            cant_f   = float(cant)
            precio_f = float(precio)
            det = DetalleCompra(compra=compra, cantidad=cant_f, precio_unitario=precio_f)

            if tipo == 'producto':
                det.producto_id = id_
                prod = Producto.objects.get(pk=id_)
                prod.stock += int(cant_f)
                prod.save(update_fields=['stock'])
                MovimientoInventario.objects.create(
                    producto=prod, tipo='entrada',
                    cantidad=int(cant_f),
                    nota=nota or f'Compra #{compra.pk}',
                    compra=compra
                )
            else:
                det.ingrediente_id = id_
                ing = Ingrediente.objects.get(pk=id_)
                ing.stock = float(ing.stock) + cant_f
                ing.save(update_fields=['stock'])
                MovimientoIngrediente.objects.create(
                    ingrediente=ing, tipo='entrada',
                    cantidad=cant_f,
                    nota=nota or f'Compra #{compra.pk}',
                    compra=compra
                )
            det.save()
            total += cant_f * precio_f

        compra.total = total
        compra.save(update_fields=['total'])
        messages.success(request, f'Entrada registrada. Compra #{compra.pk} — Total: ${total:,.0f}')
        return redirect('app_admin:proveedor_compras', pk=prov_id)

    # Auto-select proveedor: producto_sel o ingrediente_sel tienen proveedor asociado
    prov_autosel = ''
    if producto_sel and producto_sel.proveedor:
        prov_autosel = str(producto_sel.proveedor.pk)
    elif ingrediente_sel and ingrediente_sel.proveedor:
        prov_autosel = str(ingrediente_sel.proveedor.pk)

    return render(request, 'app_admin/entrada_stock.html', _ctx({
        'proveedores':     proveedores,
        'productos':       productos,
        'ingredientes':    ingredientes,
        'producto_sel':    producto_sel,
        'ingrediente_sel': ingrediente_sel,
        'prov_get_pk':     request.GET.get('prov', '') or prov_autosel,
    }))


@admin_required
def salida_stock(request):
    """Registrar salida/merma de stock para productos o ingredientes."""
    productos    = Producto.objects.filter(tipo='simple').select_related('proveedor')
    ingredientes = Ingrediente.objects.filter(activo=True).select_related('proveedor')

    # Pre-selección via GET params: ?tipo=ingrediente&item=<pk>
    item_tipo_sel = request.GET.get('tipo', 'ingrediente')
    item_pk_sel   = request.GET.get('item', '')

    if request.method == 'POST':
        tipo_item = request.POST.get('item_tipo', 'ingrediente')
        item_id   = request.POST.get('item_id', '').strip()
        cantidad  = request.POST.get('cantidad', '0').strip()
        motivo    = request.POST.get('motivo', 'salida')
        nota      = request.POST.get('nota', '').strip()

        try:
            cantidad = float(cantidad)
        except ValueError:
            cantidad = 0

        if not item_id or cantidad <= 0:
            messages.error(request, 'Selecciona un ítem y especifica una cantidad mayor a 0.')
        else:
            try:
                if tipo_item == 'producto':
                    prod = get_object_or_404(Producto, pk=item_id)
                    # Para productos: usar enteros (truncar cantidad)
                    cantidad_int = int(cantidad)
                    prod.stock = max(0, prod.stock - cantidad_int)
                    prod.save(update_fields=['stock'])
                    MovimientoInventario.objects.create(
                        producto=prod, tipo=motivo,
                        cantidad=cantidad, nota=nota
                    )
                    messages.success(request, f'Salida de "{prod.nombre}" registrada. Stock actual: {prod.stock}')
                else:
                    ing = get_object_or_404(Ingrediente, pk=item_id)
                    # Para ingredientes: usar decimales
                    ing.stock = max(0, float(ing.stock) - cantidad)
                    ing.save(update_fields=['stock'])
                    MovimientoIngrediente.objects.create(
                        ingrediente=ing, tipo=motivo,
                        cantidad=cantidad, nota=nota
                    )
                    messages.success(request, f'Salida de "{ing.nombre}" registrada. Stock actual: {ing.stock}')
                return redirect('app_admin:inventario')
            except Exception as e:
                messages.error(request, f'Error al registrar la salida: {str(e)}')

    productos_json = json.dumps([
        {'id': p.pk, 'nombre': p.nombre, 'stock': p.stock, 'unidad': 'und'}
        for p in productos
    ])
    ingredientes_json = json.dumps([
        {'id': ing.pk, 'nombre': ing.nombre, 'stock': float(ing.stock), 'unidad': ing.get_unidad_display()}
        for ing in ingredientes
    ])

    return render(request, 'app_admin/salida_stock.html', _ctx({
        'productos_json':    productos_json,
        'ingredientes_json': ingredientes_json,
        'item_tipo_sel':     item_tipo_sel,
        'item_pk_sel':       item_pk_sel,
    }))


@admin_required
def ingrediente_eliminar(request, pk):
    ing = get_object_or_404(Ingrediente, pk=pk)
    if request.method == 'POST':
        nombre = ing.nombre
        ing.activo = False
        ing.save(update_fields=['activo'])
        messages.success(request, f'Ingrediente "{nombre}" desactivado del inventario.')
    return redirect('app_admin:inventario')


# ══════════════════════════════════════════════════════════════════════════════
# INGREDIENTES
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def ingredientes(request):
    qs  = Ingrediente.objects.select_related('proveedor').filter(activo=True)
    q   = request.GET.get('q', '').strip()
    if q: qs = qs.filter(Q(nombre__icontains=q) | Q(proveedor__nombre__icontains=q))

    movimientos = MovimientoIngrediente.objects.select_related(
        'ingrediente', 'compra__proveedor'
    ).order_by('-fecha')[:50]

    # KPI counts — evaluated once from the full (unfiltered) queryset
    todos = Ingrediente.objects.filter(activo=True)
    kpi = {
        'sin_stock':     sum(1 for i in todos if i.sin_stock),
        'stock_bajo':    sum(1 for i in todos if i.stock_bajo and not i.sin_stock),
        'con_proveedor': todos.filter(proveedor__isnull=False).count(),
    }

    return render(request, 'app_admin/ingredientes.html', _ctx({
        'ingredientes': qs,
        'movimientos':  movimientos,
        'q':  q,
        'kpi': kpi,
    }))


@admin_required
def ingrediente_nuevo(request):
    proveedores = Proveedor.objects.filter(activo=True)
    if request.method == 'POST':
        nombre    = request.POST.get('nombre', '').strip()
        unidad    = request.POST.get('unidad')
        precio    = request.POST.get('precio_unitario')
        stock     = request.POST.get('stock', 0)
        stock_min = request.POST.get('stock_minimo', 0)
        prov_id   = request.POST.get('proveedor') or None
        f_venc    = request.POST.get('fecha_vencimiento') or None
        imagen    = request.FILES.get('imagen')

        if not nombre or not precio:
            messages.error(request, 'Nombre y precio son obligatorios.')
        else:
            Ingrediente.objects.create(
                nombre=nombre, unidad=unidad, precio_unitario=precio,
                stock=stock, stock_minimo=stock_min, proveedor_id=prov_id,
                fecha_vencimiento=f_venc, imagen=imagen,
            )
            messages.success(request, f'Ingrediente "{nombre}" creado.')
            return redirect('app_admin:ingredientes')

    return render(request, 'app_admin/ingrediente_form.html', _ctx({
        'proveedores': proveedores, 'accion': 'Nuevo ingrediente',
    }))


@admin_required
def ingrediente_editar(request, pk):
    ing         = get_object_or_404(Ingrediente, pk=pk)
    proveedores = Proveedor.objects.filter(activo=True)
    if request.method == 'POST':
        ing.nombre          = request.POST.get('nombre', ing.nombre).strip()
        ing.unidad          = request.POST.get('unidad', ing.unidad)
        ing.precio_unitario = request.POST.get('precio_unitario', ing.precio_unitario)
        ing.stock_minimo    = request.POST.get('stock_minimo', ing.stock_minimo)
        ing.proveedor_id    = request.POST.get('proveedor') or None
        ing.fecha_vencimiento = request.POST.get('fecha_vencimiento') or None
        if request.FILES.get('imagen'):
            ing.imagen = request.FILES['imagen']
        ing.save()
        messages.success(request, f'Ingrediente "{ing.nombre}" actualizado.')
        return redirect('app_admin:ingredientes')

    return render(request, 'app_admin/ingrediente_form.html', _ctx({
        'ingrediente': ing, 'proveedores': proveedores, 'accion': 'Editar ingrediente',
    }))


@admin_required
def ingrediente_ajuste(request, pk):
    ing = get_object_or_404(Ingrediente, pk=pk)
    if request.method == 'POST':
        tipo     = request.POST.get('tipo', 'ajuste')
        cantidad = float(request.POST.get('cantidad', 0))
        nota     = request.POST.get('nota', '').strip()

        if tipo == 'entrada':
            ing.stock = float(ing.stock) + cantidad
        elif tipo in ['salida', 'merma']:
            ing.stock = max(0, float(ing.stock) - cantidad)
        elif tipo == 'ajuste':
            ing.stock = cantidad

        ing.save(update_fields=['stock'])
        MovimientoIngrediente.objects.create(ingrediente=ing, tipo=tipo, cantidad=cantidad, nota=nota)
        messages.success(request, f'Stock de "{ing.nombre}" actualizado.')
    return redirect('app_admin:ingredientes')


@admin_required
def ingrediente_historial(request, pk):
    ing         = get_object_or_404(Ingrediente, pk=pk)
    movimientos = ing.movimientos.select_related('compra__proveedor').order_by('-fecha')
    return render(request, 'app_admin/ingrediente_historial.html', _ctx({
        'ingrediente': ing,
        'movimientos': movimientos,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL UNIFICADO
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def historial(request):
    return render(request, 'app_admin/historial.html', _ctx())


@admin_required
def historial_api(request):
    """API JSON para el historial unificado con filtros."""
    tipo_f  = request.GET.get('tipo', '')     # 'producto' | 'ingrediente'
    mov_f   = request.GET.get('mov', '')      # entrada | salida | ajuste | merma
    desde   = request.GET.get('desde', '')
    hasta   = request.GET.get('hasta', '')
    q       = request.GET.get('q', '').strip()

    resultados = []

    # Movimientos de productos
    if tipo_f in ('', 'producto'):
        qs = MovimientoInventario.objects.select_related(
            'producto__proveedor', 'compra__proveedor'
        ).order_by('-fecha')
        if mov_f:   qs = qs.filter(tipo=mov_f)
        if desde:   qs = qs.filter(fecha__date__gte=desde)
        if hasta:   qs = qs.filter(fecha__date__lte=hasta)
        if q:       qs = qs.filter(producto__nombre__icontains=q)
        for m in qs[:200]:
            # Proveedor: 1) el de la compra vinculada, 2) el registrado en el producto
            if m.compra and m.compra.proveedor:
                prov = m.compra.proveedor.nombre
            elif m.producto.proveedor:
                prov = m.producto.proveedor.nombre
            else:
                prov = '—'
            resultados.append({
                'categoria': 'Producto',
                'nombre':    m.producto.nombre,
                'tipo':      m.get_tipo_display(),
                'tipo_raw':  m.tipo,
                'cantidad':  float(m.cantidad),
                'proveedor': prov,
                'nota':      m.nota,
                'fecha':     m.fecha.strftime('%d/%m/%Y %H:%M'),
                'fecha_iso': m.fecha.isoformat(),
            })

    # Movimientos de ingredientes
    if tipo_f in ('', 'ingrediente'):
        qs = MovimientoIngrediente.objects.select_related(
            'ingrediente__proveedor', 'compra__proveedor'
        ).order_by('-fecha')
        if mov_f:   qs = qs.filter(tipo=mov_f)
        if desde:   qs = qs.filter(fecha__date__gte=desde)
        if hasta:   qs = qs.filter(fecha__date__lte=hasta)
        if q:       qs = qs.filter(ingrediente__nombre__icontains=q)
        for m in qs[:200]:
            # Proveedor: 1) el de la compra vinculada, 2) el registrado en el ingrediente
            if m.compra and m.compra.proveedor:
                prov = m.compra.proveedor.nombre
            elif m.ingrediente.proveedor:
                prov = m.ingrediente.proveedor.nombre
            else:
                prov = '—'
            resultados.append({
                'categoria': 'Ingrediente',
                'nombre':    m.ingrediente.nombre,
                'tipo':      m.get_tipo_display(),
                'tipo_raw':  m.tipo,
                'cantidad':  float(m.cantidad),
                'proveedor': prov,
                'nota':      m.nota,
                'fecha':     m.fecha.strftime('%d/%m/%Y %H:%M'),
                'fecha_iso': m.fecha.isoformat(),
            })

    # Ordenar por fecha ISO (formato sortable); la cadena dd/mm/YYYY no lo es
    resultados.sort(key=lambda x: x['fecha_iso'], reverse=True)
    return JsonResponse({'data': resultados[:300]})


# ══════════════════════════════════════════════════════════════════════════════
# CALENDARIO DE MOVIMIENTOS
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def calendario(request):
    return render(request, 'app_admin/calendario.html', _ctx())


@admin_required
def calendario_api(request):
    """Devuelve movimientos agrupados por fecha para FullCalendar."""
    desde = request.GET.get('start', str(date.today().replace(day=1)))[:10]
    hasta = request.GET.get('end',   str(date.today()))[:10]

    eventos = []

    # Entradas de productos
    for m in MovimientoInventario.objects.filter(
        fecha__date__gte=desde, fecha__date__lte=hasta, tipo='entrada'
    ).select_related('producto'):
        eventos.append({
            'title':           f'+{int(m.cantidad)} {m.producto.nombre}',
            'start':           m.fecha.strftime('%Y-%m-%d'),
            'backgroundColor': '#2d6a4f',
            'borderColor':     '#2d6a4f',
            'textColor':       '#fff',
            'extendedProps':   {'tipo': 'entrada', 'cat': 'Producto'},
        })

    # Salidas de productos
    for m in MovimientoInventario.objects.filter(
        fecha__date__gte=desde, fecha__date__lte=hasta, tipo__in=['salida', 'merma']
    ).select_related('producto'):
        eventos.append({
            'title':           f'-{int(m.cantidad)} {m.producto.nombre}',
            'start':           m.fecha.strftime('%Y-%m-%d'),
            'backgroundColor': '#d94f3d',
            'borderColor':     '#d94f3d',
            'textColor':       '#fff',
            'extendedProps':   {'tipo': m.tipo, 'cat': 'Producto'},
        })

    # Movimientos de ingredientes
    for m in MovimientoIngrediente.objects.filter(
        fecha__date__gte=desde, fecha__date__lte=hasta
    ).select_related('ingrediente'):
        color = '#1a56db' if m.tipo == 'entrada' else '#e07b2a'
        eventos.append({
            'title':           f'Ing: {m.ingrediente.nombre}',
            'start':           m.fecha.strftime('%Y-%m-%d'),
            'backgroundColor': color,
            'borderColor':     color,
            'textColor':       '#fff',
            'extendedProps':   {'tipo': m.tipo, 'cat': 'Ingrediente'},
        })

    # Pedidos entregados
    for p in Pedido.objects.filter(
        fecha_pedido__date__gte=desde, fecha_pedido__date__lte=hasta, estado='entregado'
    ):
        eventos.append({
            'title':           f'Pedido {p.ticket}',
            'start':           p.fecha_pedido.strftime('%Y-%m-%d'),
            'backgroundColor': '#7c3aed',
            'borderColor':     '#7c3aed',
            'textColor':       '#fff',
            'extendedProps':   {'tipo': 'pedido', 'cat': 'Venta'},
        })

    return JsonResponse(eventos, safe=False)


# ══════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def proveedores(request):
    q  = request.GET.get('q', '').strip()
    qs = Proveedor.objects.annotate(
        num_productos=Count('productos', distinct=True),
        num_compras=Count('compras', distinct=True),
    ).order_by('nombre')
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(nit__icontains=q) | Q(contacto__icontains=q))
    return render(request, 'app_admin/proveedores.html', _ctx({'proveedores': qs, 'q': q}))


@admin_required
def proveedor_nuevo(request):
    if request.method == 'POST':
        nombre    = request.POST.get('nombre', '').strip()
        if not nombre:
            messages.error(request, 'El nombre es obligatorio.')
        else:
            p = Proveedor.objects.create(
                nombre=nombre,
                nit=request.POST.get('nit', '').strip(),
                contacto=request.POST.get('contacto', '').strip(),
                telefono=request.POST.get('telefono', '').strip(),
                email=request.POST.get('email', '').strip(),
                direccion=request.POST.get('direccion', '').strip(),
                logo=request.FILES.get('logo'),
            )
            messages.success(request, f'Proveedor "{p.nombre}" creado.')
            return redirect('app_admin:proveedores')
    return render(request, 'app_admin/proveedor_form.html', _ctx({'accion': 'Nuevo proveedor'}))


@admin_required
def proveedor_editar(request, pk):
    prov = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        prov.nombre    = request.POST.get('nombre', prov.nombre).strip()
        prov.nit       = request.POST.get('nit', '').strip()
        prov.contacto  = request.POST.get('contacto', '').strip()
        prov.telefono  = request.POST.get('telefono', '').strip()
        prov.email     = request.POST.get('email', '').strip()
        prov.direccion = request.POST.get('direccion', '').strip()
        if request.FILES.get('logo'):
            prov.logo = request.FILES['logo']
        prov.save()
        messages.success(request, f'Proveedor "{prov.nombre}" actualizado.')
        return redirect('app_admin:proveedores')
    return render(request, 'app_admin/proveedor_form.html', _ctx({'proveedor': prov, 'accion': 'Editar proveedor'}))


@admin_required
def proveedor_compras(request, pk):
    prov    = get_object_or_404(Proveedor, pk=pk)
    compras = prov.compras.prefetch_related(
        'detalles__producto', 'detalles__ingrediente'
    ).order_by('-fecha')
    return render(request, 'app_admin/proveedor_compras.html', _ctx({
        'proveedor': prov, 'compras': compras,
    }))


@admin_required
def proveedor_stats(request, pk):
    """Estadísticas mensuales del proveedor."""
    prov = get_object_or_404(Proveedor, pk=pk)
    # Compras de los últimos 12 meses agrupadas por mes
    from django.db.models.functions import TruncMonth
    datos = prov.compras.annotate(mes=TruncMonth('fecha')).values('mes').annotate(
        total=Sum('total')
    ).order_by('mes')
    return JsonResponse({
        'labels': [d['mes'].strftime('%b %Y') for d in datos],
        'values': [float(d['total']) for d in datos],
    })


@admin_required
def compra_nueva(request, prov_pk=None):
    proveedores  = Proveedor.objects.filter(activo=True)
    productos    = Producto.objects.filter(tipo='simple')
    ingredientes = Ingrediente.objects.filter(activo=True)
    prov_sel     = get_object_or_404(Proveedor, pk=prov_pk) if prov_pk else None

    if request.method == 'POST':
        # Redirigir a la entrada unificada con los mismos datos
        return redirect('app_admin:entrada_stock')

    return render(request, 'app_admin/entrada_stock.html', _ctx({
        'proveedores': proveedores, 'productos': productos,
        'ingredientes': ingredientes, 'prov_sel': prov_sel,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def pedidos(request):
    hoy   = date.today()
    fecha = request.GET.get('fecha', str(hoy))
    q     = request.GET.get('q', '').strip()

    qs = Pedido.objects.filter(fecha_pedido__date=fecha).select_related(
        'estudiante__perfil__user'
    ).prefetch_related('detalles__producto')

    if q:
        qs = qs.filter(
            Q(ticket__icontains=q) |
            Q(estudiante__perfil__user__first_name__icontains=q) |
            Q(estudiante__perfil__user__last_name__icontains=q)
        )

    kanban = {
        'pendiente':  qs.filter(estado='pendiente'),
        'preparando': qs.filter(estado='preparando'),
        'listo':      qs.filter(estado='listo'),
        'entregado':  qs.filter(estado='entregado'),
        'cancelado':  qs.filter(estado='cancelado'),
    }
    return render(request, 'app_admin/pedidos.html', _ctx({
        'kanban':    kanban,
        'pedidos':   qs,
        'estados':   Pedido.ESTADO_CHOICES,
        'fecha':     fecha,
        'fecha_hoy': hoy,
        'q':         q,
    }))


@admin_required
def pedido_detalle(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related('estudiante__perfil__user')
                      .prefetch_related('detalles__producto'),
        pk=pk
    )
    return render(request, 'app_admin/pedido_detalle.html', _ctx({'pedido': pedido}))


@admin_required
def pedido_estado(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if request.method == 'POST':
        nuevo = request.POST.get('estado')
        if nuevo not in [e[0] for e in Pedido.ESTADO_CHOICES]:
            messages.error(request, 'Estado no válido.')
            return redirect(request.POST.get('next', 'app_admin:pedidos'))

        pedido.estado = nuevo
        if nuevo == 'entregado':
            pedido.fecha_entrega = timezone.now()
            # Descontar stock
            for detalle in pedido.detalles.select_related('producto').all():
                if detalle.producto.tipo == 'elaborado':
                    for r in detalle.producto.receta.all():
                        r.ingrediente.stock = max(
                            0, float(r.ingrediente.stock) - float(r.cantidad) * detalle.cantidad
                        )
                        r.ingrediente.save(update_fields=['stock'])
                        MovimientoIngrediente.objects.create(
                            ingrediente=r.ingrediente, tipo='salida',
                            cantidad=float(r.cantidad) * detalle.cantidad,
                            nota=f'Pedido {pedido.ticket}'
                        )
                else:
                    detalle.producto.stock = max(0, detalle.producto.stock - detalle.cantidad)
                    detalle.producto.save(update_fields=['stock'])
                    MovimientoInventario.objects.create(
                        producto=detalle.producto, tipo='salida',
                        cantidad=detalle.cantidad, nota=f'Pedido {pedido.ticket}'
                    )
        pedido.save(update_fields=['estado', 'fecha_entrega'])
        messages.success(request, f'Pedido {pedido.ticket} → {pedido.get_estado_display()}')
    return redirect(request.POST.get('next', 'app_admin:pedidos'))


# ══════════════════════════════════════════════════════════════════════════════
# USUARIOS
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def usuarios(request):
    perfiles = Perfil.objects.select_related('user').order_by('rol', 'user__last_name')
    rol_f    = request.GET.get('rol', '')
    if rol_f: perfiles = perfiles.filter(rol=rol_f)
    return render(request, 'app_admin/usuarios.html', _ctx({
        'perfiles': perfiles, 'rol_f': rol_f, 'roles': Perfil.ROL_CHOICES,
    }))


@admin_required
def usuario_toggle(request, pk):
    perfil = get_object_or_404(Perfil, pk=pk)
    if request.method == 'POST':
        perfil.activo = not perfil.activo
        perfil.save(update_fields=['activo'])
        messages.success(request, f'Usuario {perfil.user.username} {"activado" if perfil.activo else "desactivado"}.')
    return redirect('app_admin:usuarios')


@admin_required
def usuario_detalle(request, pk):
    perfil  = get_object_or_404(Perfil.objects.select_related('user'), pk=pk)
    context = _ctx({'perfil': perfil})
    if perfil.rol == 'estudiante':
        try:
            context['estudiante'] = perfil.estudiante
            context['pedidos']    = perfil.estudiante.pedidos.order_by('-fecha_pedido')[:10]
        except: pass
    elif perfil.rol == 'padre':
        try:
            context['padre'] = perfil.padre
            context['hijos'] = perfil.padre.hijos.select_related('perfil__user').all()
        except: pass
    return render(request, 'app_admin/usuario_detalle.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def estadisticas(request):
    rango = request.GET.get('rango', '7')
    hoy   = date.today()
    desde = hoy - timedelta(days=int(rango))

    pedidos = Pedido.objects.filter(fecha_pedido__date__gte=desde, estado='entregado')
    ingresos  = float(pedidos.aggregate(t=Sum('total'))['t'] or 0)
    costos    = float(pedidos.aggregate(t=Sum('costo_total'))['t'] or 0)
    ganancia  = ingresos - costos
    margen    = round((ganancia / ingresos) * 100, 1) if ingresos else 0
    n_pedidos = pedidos.count()

    top_productos = DetallePedido.objects.filter(pedido__in=pedidos).values(
        nombre=F('producto__nombre')
    ).annotate(
        unidades=Sum('cantidad'),
        ingresos=Sum(F('cantidad') * F('precio_unitario')),
        costos=Sum(F('cantidad') * F('costo_unitario')),
    ).order_by('-unidades')[:10]

    for p in top_productos:
        p['ganancia'] = float(p['ingresos'] or 0) - float(p['costos'] or 0)

    return render(request, 'app_admin/estadisticas.html', _ctx({
        'ingresos': ingresos, 'costos': costos, 'ganancia': ganancia,
        'margen': margen, 'n_pedidos': n_pedidos,
        'top_productos': top_productos, 'rango': rango, 'desde': desde,
    }))


@admin_required
def api_ventas(request):
    dias  = int(request.GET.get('dias', 7))
    hoy   = date.today()
    labels, ingresos_data, ganancia_data = [], [], []
    for i in range(dias - 1, -1, -1):
        d   = hoy - timedelta(days=i)
        ped = Pedido.objects.filter(fecha_pedido__date=d, estado='entregado')
        ing = float(ped.aggregate(t=Sum('total'))['t'] or 0)
        cos = float(ped.aggregate(t=Sum('costo_total'))['t'] or 0)
        labels.append(d.strftime('%d/%m'))
        ingresos_data.append(ing)
        ganancia_data.append(round(ing - cos, 2))
    return JsonResponse({'labels': labels, 'ingresos': ingresos_data, 'ganancia': ganancia_data})


@admin_required
def api_categorias(request):
    dias  = int(request.GET.get('dias', 7))
    desde = date.today() - timedelta(days=dias)
    data  = DetallePedido.objects.filter(
        pedido__fecha_pedido__date__gte=desde, pedido__estado='entregado'
    ).values(cat=F('producto__categoria__nombre')).annotate(
        total=Sum(F('cantidad') * F('precio_unitario'))
    ).order_by('-total')
    return JsonResponse({
        'labels': [d['cat'] for d in data],
        'values': [float(d['total'] or 0) for d in data],
    })


@admin_required
def api_productos_top(request):
    dias  = int(request.GET.get('dias', 7))
    desde = date.today() - timedelta(days=dias)
    data  = DetallePedido.objects.filter(
        pedido__fecha_pedido__date__gte=desde, pedido__estado='entregado'
    ).values(nombre=F('producto__nombre')).annotate(
        unidades=Sum('cantidad')
    ).order_by('-unidades')[:8]
    return JsonResponse({
        'labels': [d['nombre'] for d in data],
        'values': [d['unidades'] for d in data],
    })


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def exportar_excel(request):
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        messages.error(request, 'openpyxl no está instalado. Ejecuta: pip install openpyxl')
        return redirect('app_admin:inventario')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Inventario'

    # Estilo cabecera
    header_fill = PatternFill(start_color='1a3d2b', end_color='1a3d2b', fill_type='solid')
    header_font = Font(color='FFFFFF', bold=True)

    headers = ['Nombre', 'Categoría', 'Tipo', 'Proveedor',
               'Precio Costo', 'Precio Venta', 'Ganancia', 'Margen %', 'Stock', 'Stock Mínimo', 'Disponible']
    ws.append(headers)
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    for p in Producto.objects.select_related('categoria', 'proveedor').all():
        ws.append([
            p.nombre,
            str(p.categoria),
            p.get_tipo_display(),
            str(p.proveedor) if p.proveedor else '—',
            float(p.precio_costo or 0),
            float(p.precio_venta),
            p.ganancia,
            p.margen,
            p.stock if p.tipo == 'simple' else '—',
            p.stock_minimo if p.tipo == 'simple' else '—',
            'Sí' if p.disponible else 'No',
        ])

    # Ajustar anchos
    for col in ws.columns:
        max_len = max(len(str(c.value or '')) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 30)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inventario_punto_asis.xlsx"'
    wb.save(response)
    return response


@admin_required
def exportar_pdf(request):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        import io
    except ImportError:
        messages.error(request, 'reportlab no está instalado. Ejecuta: pip install reportlab')
        return redirect('app_admin:inventario')

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Título
    elements.append(Paragraph('Inventario — Punto Asis', styles['Title']))
    elements.append(Paragraph(f'Generado: {date.today().strftime("%d/%m/%Y")}', styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Tabla
    headers = ['Nombre', 'Categoría', 'Tipo', 'Proveedor',
               'P. Costo', 'P. Venta', 'Ganancia', 'Margen%', 'Stock']
    data = [headers]
    for p in Producto.objects.select_related('categoria', 'proveedor').all():
        data.append([
            p.nombre[:25],
            str(p.categoria),
            p.get_tipo_display()[:10],
            str(p.proveedor)[:15] if p.proveedor else '—',
            f'${float(p.precio_costo or 0):,.0f}',
            f'${float(p.precio_venta):,.0f}',
            f'${p.ganancia:,.0f}',
            f'{p.margen}%',
            str(p.stock) if p.tipo == 'simple' else '—',
        ])

    verde_oscuro = colors.HexColor('#1a3d2b')
    tabla = Table(data, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), verde_oscuro),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f2ef')]),
        ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e2dd')),
        ('ALIGN',      (4, 0), (-1, -1), 'RIGHT'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(tabla)
    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventario_punto_asis.pdf"'
    return response


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL Y CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def perfil(request):
    perfil_auth = request.user.perfil
    perfil_admin, _ = PerfilAdmin.objects.get_or_create(perfil=perfil_auth)

    if request.method == 'POST':
        u = request.user
        u.first_name = request.POST.get('first_name', u.first_name).strip()
        u.last_name  = request.POST.get('last_name',  u.last_name).strip()
        u.email      = request.POST.get('email', u.email).strip()
        u.save(update_fields=['first_name', 'last_name', 'email'])

        perfil_auth.telefono = request.POST.get('telefono', '').strip()
        perfil_auth.save(update_fields=['telefono'])

        perfil_admin.documento        = request.POST.get('documento', '').strip()
        perfil_admin.direccion        = request.POST.get('direccion', '').strip()
        perfil_admin.cargo            = request.POST.get('cargo', '').strip()
        fecha_nac = request.POST.get('fecha_nacimiento') or None
        perfil_admin.fecha_nacimiento = fecha_nac
        if request.FILES.get('foto'):
            perfil_admin.foto = request.FILES['foto']
        perfil_admin.save()

        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('app_admin:perfil')

    return render(request, 'app_admin/perfil.html', _ctx({
        'perfil_auth':  perfil_auth,
        'perfil_admin': perfil_admin,
    }))


@admin_required
def configuracion(request):
    return render(request, 'app_admin/configuracion.html', _ctx())


# ══════════════════════════════════════════════════════════════════════════════
# ALERTAS API (para topbar)
# ══════════════════════════════════════════════════════════════════════════════

@admin_required
def api_alertas(request):
    alertas = _get_alertas()

    detalle = []

    for p in Producto.objects.filter(tipo='simple', stock__lte=F('stock_minimo')).select_related('proveedor')[:5]:
        detalle.append({
            'tipo': 'stock_producto',
            'texto': f'{p.nombre} — {p.stock} uds. (mín: {p.stock_minimo})',
            'url': f'/admin-panel/inventario/',
            'color': 'amber',
        })

    for i in Ingrediente.objects.filter(activo=True, stock__lte=F('stock_minimo')).select_related('proveedor')[:5]:
        detalle.append({
            'tipo': 'stock_ingrediente',
            'texto': f'{i.nombre} — {i.stock} {i.unidad} (mín: {i.stock_minimo})',
            'url': f'/admin-panel/inventario/ingredientes/',
            'color': 'amber',
        })

    for i in Ingrediente.objects.filter(activo=True, fecha_vencimiento__lt=date.today())[:3]:
        detalle.append({
            'tipo': 'vencido',
            'texto': f'{i.nombre} venció el {i.fecha_vencimiento.strftime("%d/%m/%Y")}',
            'url': f'/admin-panel/inventario/ingredientes/',
            'color': 'red',
        })

    for i in Ingrediente.objects.filter(
        activo=True,
        fecha_vencimiento__gte=date.today(),
        fecha_vencimiento__lte=date.today() + timedelta(days=7)
    )[:3]:
        detalle.append({
            'tipo': 'vence_pronto',
            'texto': f'{i.nombre} vence el {i.fecha_vencimiento.strftime("%d/%m/%Y")}',
            'url': f'/admin-panel/inventario/ingredientes/',
            'color': 'amber',
        })

    alertas['detalle'] = detalle
    return JsonResponse(alertas)
