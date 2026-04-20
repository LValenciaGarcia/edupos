import csv
import io
import json
from decimal import Decimal
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Avg, Q, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from authentication.models import Perfil, Docente
from app_admin.models import Producto, Categoria, DetallePedido
from .models import (
    PedidoDocente, DetallePedidoDocente,
    PedidoProgramadoDocente, DetalleProgramadoDocente,
    FavoritoDocente, ReseñaProducto,
    PedidoGrupal, NotificacionDocente,
    RecargaDocente,
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def docente_required(view_func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        try:
            if request.user.perfil.rol != 'docente':
                messages.error(request, 'Acceso restringido a docentes.')
                return redirect('authentication:login')
        except Perfil.DoesNotExist:
            return redirect('authentication:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _get_docente(request):
    return get_object_or_404(Docente, perfil=request.user.perfil)


def _n_notif(docente):
    return NotificacionDocente.objects.filter(docente=docente, leida=False).count()


def _ctx(docente, extra=None):
    ctx = {'n_notif': _n_notif(docente)}
    if extra:
        ctx.update(extra)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def dashboard(request):
    docente = _get_docente(request)
    ahora = timezone.now()

    pedidos_activos = PedidoDocente.objects.filter(
        docente=docente,
        estado__in=['pendiente', 'preparando', 'listo'],
    ).prefetch_related('detalles__producto')

    gasto_mes = PedidoDocente.objects.filter(
        docente=docente, estado='entregado',
        fecha_pedido__month=ahora.month, fecha_pedido__year=ahora.year,
    ).aggregate(t=Sum('total'))['t'] or 0

    gasto_hoy = PedidoDocente.objects.filter(
        docente=docente, estado='entregado',
        fecha_pedido__date=ahora.date(),
    ).aggregate(t=Sum('total'))['t'] or 0

    total_pedidos = PedidoDocente.objects.filter(docente=docente, estado='entregado').count()

    # Pedidos grupales abiertos (de otros docentes para unirse)
    grupales_abiertos = PedidoGrupal.objects.filter(estado='abierto').exclude(
        organizador=docente
    ).exclude(
        pedidos_miembros__docente=docente
    )[:5]

    # Próximos programados
    programados = PedidoProgramadoDocente.objects.filter(
        docente=docente, estado='activo',
        fecha_entrega__gte=ahora.date(),
    ).order_by('fecha_entrega')[:3]

    # Producto más pedido
    top_producto = (
        DetallePedidoDocente.objects.filter(pedido__docente=docente, pedido__estado='entregado')
        .values('producto__nombre')
        .annotate(total_cant=Sum('cantidad'))
        .order_by('-total_cant')
        .first()
    )

    # Favoritos rápidos
    favoritos = FavoritoDocente.objects.filter(
        docente=docente
    ).select_related('producto').order_by('-created_at')[:6]

    return render(request, 'app_docente/dashboard.html', _ctx(docente, {
        'docente':          docente,
        'pedidos_activos':  pedidos_activos,
        'gasto_mes':        gasto_mes,
        'gasto_hoy':        gasto_hoy,
        'total_pedidos':    total_pedidos,
        'grupales_abiertos':grupales_abiertos,
        'programados':      programados,
        'top_producto':     top_producto,
        'favoritos':        favoritos,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# MENÚ / PEDIR
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def menu(request):
    docente = _get_docente(request)
    categorias = Categoria.objects.filter(activa=True)
    cat_filter = request.GET.get('cat')
    busqueda   = request.GET.get('q', '').strip()

    productos = Producto.objects.filter(disponible=True).select_related('categoria')
    if cat_filter:
        productos = productos.filter(categoria__nombre=cat_filter)
    if busqueda:
        productos = productos.filter(nombre__icontains=busqueda)

    # IDs de favoritos del docente
    favoritos_ids = set(
        FavoritoDocente.objects.filter(docente=docente).values_list('producto_id', flat=True)
    )

    # Reseñas propias del docente
    reseñas_propias = {
        r.producto_id: r
        for r in ReseñaProducto.objects.filter(docente=docente)
    }

    # Promedio de reseñas por producto
    promedios = {
        r['producto_id']: r['avg']
        for r in ReseñaProducto.objects.values('producto_id').annotate(avg=Avg('calificacion'))
    }

    productos_data = []
    for p in productos:
        productos_data.append({
            'producto':    p,
            'es_favorito': p.pk in favoritos_ids,
            'mi_reseña':   reseñas_propias.get(p.pk),
            'promedio':    promedios.get(p.pk),
        })

    return render(request, 'app_docente/menu.html', _ctx(docente, {
        'docente':        docente,
        'categorias':     categorias,
        'cat_filter':     cat_filter,
        'busqueda':       busqueda,
        'productos_data': productos_data,
    }))


@docente_required
@require_POST
def pedir(request):
    """Recibe el carrito desde el menú y muestra confirmación."""
    docente = _get_docente(request)
    carrito_raw = request.POST.get('carrito', '[]')
    try:
        carrito = json.loads(carrito_raw)
    except json.JSONDecodeError:
        messages.error(request, 'Error en el carrito.')
        return redirect('app_docente:menu')

    if not carrito:
        messages.error(request, 'El carrito está vacío.')
        return redirect('app_docente:menu')

    items = []
    total = Decimal('0')
    for item in carrito:
        try:
            p = Producto.objects.get(pk=item['id'], disponible=True)
            cant = max(int(item.get('cantidad', 1)), 1)
            subtotal = p.precio_venta * cant
            items.append({'producto': p, 'cantidad': cant, 'subtotal': subtotal})
            total += subtotal
        except (Producto.DoesNotExist, KeyError, ValueError):
            continue

    if not items:
        messages.error(request, 'No hay productos válidos en el carrito.')
        return redirect('app_docente:menu')

    # Guardar en sesión para confirmar
    request.session['carrito_docente'] = carrito_raw
    request.session['nota_docente'] = request.POST.get('nota', '')

    return render(request, 'app_docente/confirmar_pedido.html', _ctx(docente, {
        'docente': docente,
        'items':   items,
        'total':   total,
    }))


@docente_required
@require_POST
def confirmar_pedido(request):
    docente = _get_docente(request)
    carrito_raw = request.session.get('carrito_docente', '[]')
    nota = request.session.get('nota_docente', '')
    tipo_pago = request.POST.get('tipo_pago', 'saldo')

    try:
        carrito = json.loads(carrito_raw)
    except json.JSONDecodeError:
        messages.error(request, 'Error procesando el carrito.')
        return redirect('app_docente:menu')

    with transaction.atomic():
        pedido = PedidoDocente.objects.create(
            docente=docente,
            nota=nota,
            tipo_pago=tipo_pago,
        )
        total = Decimal('0')
        for item in carrito:
            try:
                p = Producto.objects.get(pk=item['id'], disponible=True)
                cant = max(int(item.get('cantidad', 1)), 1)
                d = DetallePedidoDocente.objects.create(
                    pedido=pedido,
                    producto=p,
                    cantidad=cant,
                    precio_unitario=p.precio_venta,
                )
                total += Decimal(str(d.subtotal))
            except (Producto.DoesNotExist, KeyError, ValueError):
                continue

        pedido.total = total
        pedido.save(update_fields=['total'])

        # Descontar saldo o acumular fiado
        if tipo_pago == 'saldo':
            docente.saldo = Decimal(str(docente.saldo)) - total
        else:
            docente.deuda_fiado = Decimal(str(docente.deuda_fiado)) + total
        docente.save(update_fields=['saldo', 'deuda_fiado'])

    # Limpiar sesión
    request.session.pop('carrito_docente', None)
    request.session.pop('nota_docente', None)

    messages.success(request, f'¡Pedido {pedido.ticket} realizado con éxito!')
    return redirect('app_docente:dashboard')


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS GRUPALES — "Sala de Profes"
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def pedidos_grupales(request):
    docente = _get_docente(request)
    abiertos = PedidoGrupal.objects.filter(estado='abierto').select_related('organizador__perfil__user')
    mis_grupales = PedidoGrupal.objects.filter(organizador=docente).order_by('-fecha')
    participando = PedidoGrupal.objects.filter(
        pedidos_miembros__docente=docente
    ).exclude(organizador=docente).distinct()

    return render(request, 'app_docente/pedidos_grupales.html', _ctx(docente, {
        'docente':       docente,
        'abiertos':      abiertos,
        'mis_grupales':  mis_grupales,
        'participando':  participando,
    }))


@docente_required
@require_POST
def crear_grupal(request):
    docente = _get_docente(request)
    titulo = request.POST.get('titulo', 'Pedido grupal sala de profes').strip()
    nota   = request.POST.get('nota', '').strip()
    grupal = PedidoGrupal.objects.create(organizador=docente, titulo=titulo, nota=nota)
    messages.success(request, f'Pedido grupal "{titulo}" creado. Comparte el enlace con tus colegas.')
    return redirect('app_docente:detalle_grupal', pk=grupal.pk)


@docente_required
def detalle_grupal(request, pk):
    docente = _get_docente(request)
    grupal = get_object_or_404(PedidoGrupal, pk=pk)
    pedidos = grupal.pedidos_miembros.select_related(
        'docente__perfil__user'
    ).prefetch_related('detalles__producto')

    ya_participa = pedidos.filter(docente=docente).exists()
    es_organizador = grupal.organizador == docente

    productos = Producto.objects.filter(disponible=True).select_related('categoria')

    return render(request, 'app_docente/detalle_grupal.html', _ctx(docente, {
        'docente':        docente,
        'grupal':         grupal,
        'pedidos':        pedidos,
        'ya_participa':   ya_participa,
        'es_organizador': es_organizador,
        'productos':      productos,
    }))


@docente_required
@require_POST
def unirse_grupal(request, pk):
    docente = _get_docente(request)
    grupal = get_object_or_404(PedidoGrupal, pk=pk, estado='abierto')

    if grupal.pedidos_miembros.filter(docente=docente).exists():
        messages.warning(request, 'Ya estás participando en este pedido grupal.')
        return redirect('app_docente:detalle_grupal', pk=pk)

    carrito_raw = request.POST.get('carrito', '[]')
    nota        = request.POST.get('nota', '')
    tipo_pago   = request.POST.get('tipo_pago', 'saldo')

    try:
        carrito = json.loads(carrito_raw)
    except json.JSONDecodeError:
        messages.error(request, 'Error en el carrito.')
        return redirect('app_docente:detalle_grupal', pk=pk)

    with transaction.atomic():
        pedido = PedidoDocente.objects.create(
            docente=docente, nota=nota, tipo_pago=tipo_pago, pedido_grupal=grupal,
        )
        total = Decimal('0')
        for item in carrito:
            try:
                p = Producto.objects.get(pk=item['id'], disponible=True)
                cant = max(int(item.get('cantidad', 1)), 1)
                d = DetallePedidoDocente.objects.create(
                    pedido=pedido, producto=p, cantidad=cant, precio_unitario=p.precio_venta,
                )
                total += Decimal(str(d.subtotal))
            except (Producto.DoesNotExist, KeyError, ValueError):
                continue
        pedido.total = total
        pedido.save(update_fields=['total'])

        if tipo_pago == 'saldo':
            docente.saldo = Decimal(str(docente.saldo)) - total
        else:
            docente.deuda_fiado = Decimal(str(docente.deuda_fiado)) + total
        docente.save(update_fields=['saldo', 'deuda_fiado'])

    messages.success(request, '¡Te uniste al pedido grupal!')
    return redirect('app_docente:detalle_grupal', pk=pk)


@docente_required
@require_POST
def cerrar_grupal(request, pk):
    docente = _get_docente(request)
    grupal = get_object_or_404(PedidoGrupal, pk=pk, organizador=docente)
    grupal.estado = 'cerrado'
    grupal.save(update_fields=['estado'])
    messages.success(request, 'Pedido grupal cerrado. Ya fue enviado a la cafetería.')
    return redirect('app_docente:pedidos_grupales')


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS PROGRAMADOS
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def programados(request):
    docente = _get_docente(request)
    activos = PedidoProgramadoDocente.objects.filter(
        docente=docente, estado='activo'
    ).prefetch_related('detalles__producto')
    historico = PedidoProgramadoDocente.objects.filter(
        docente=docente, estado__in=['procesado', 'cancelado']
    ).order_by('-created_at')[:20]
    productos = Producto.objects.filter(disponible=True).select_related('categoria')

    return render(request, 'app_docente/programados.html', _ctx(docente, {
        'docente':   docente,
        'activos':   activos,
        'historico': historico,
        'productos': productos,
    }))


@docente_required
@require_POST
def nuevo_programado(request):
    docente = _get_docente(request)
    fecha_str   = request.POST.get('fecha_entrega', '')
    hora_str    = request.POST.get('hora_entrega', '')
    nota        = request.POST.get('nota', '').strip()
    tipo_pago   = request.POST.get('tipo_pago', 'saldo')
    carrito_raw = request.POST.get('carrito', '[]')

    try:
        from datetime import date, time
        fecha = date.fromisoformat(fecha_str)
        hora  = time.fromisoformat(hora_str) if hora_str else None
        carrito = json.loads(carrito_raw)
    except (ValueError, json.JSONDecodeError):
        messages.error(request, 'Datos inválidos. Verifica la fecha y el carrito.')
        return redirect('app_docente:programados')

    if not carrito:
        messages.error(request, 'El carrito está vacío.')
        return redirect('app_docente:programados')

    with transaction.atomic():
        prog = PedidoProgramadoDocente.objects.create(
            docente=docente, fecha_entrega=fecha,
            hora_entrega=hora, nota=nota, tipo_pago=tipo_pago,
        )
        for item in carrito:
            try:
                p = Producto.objects.get(pk=item['id'], disponible=True)
                cant = max(int(item.get('cantidad', 1)), 1)
                DetalleProgramadoDocente.objects.create(pedido_prog=prog, producto=p, cantidad=cant)
            except (Producto.DoesNotExist, KeyError, ValueError):
                continue

    messages.success(request, f'Pedido programado para el {fecha.strftime("%d/%m/%Y")}.')
    return redirect('app_docente:programados')


@docente_required
@require_POST
def cancelar_programado(request, pk):
    docente = _get_docente(request)
    prog = get_object_or_404(PedidoProgramadoDocente, pk=pk, docente=docente, estado='activo')
    prog.estado = 'cancelado'
    prog.save(update_fields=['estado'])
    messages.success(request, 'Pedido programado cancelado.')
    return redirect('app_docente:programados')


@docente_required
def api_programados(request):
    docente = _get_docente(request)
    eventos = []
    for prog in PedidoProgramadoDocente.objects.filter(docente=docente, estado='activo'):
        total = prog.total
        color = '#16a34a' if prog.estado == 'activo' else '#6b6b63'
        eventos.append({
            'id':    prog.pk,
            'title': f'Pedido ${total:,.0f}',
            'start': str(prog.fecha_entrega),
            'color': color,
            'extendedProps': {
                'nota':     prog.nota,
                'tipo_pago': prog.tipo_pago,
                'items':    [f'{d.cantidad}× {d.producto.nombre}' for d in prog.detalles.all()],
            },
        })
    return JsonResponse(eventos, safe=False)


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def historial(request):
    from django.core.paginator import Paginator
    from datetime import date as date_type

    docente  = _get_docente(request)
    pedidos  = PedidoDocente.objects.filter(docente=docente).prefetch_related(
        'detalles__producto'
    ).order_by('-fecha_pedido')

    estado_f = request.GET.get('estado', '')
    fecha_f  = request.GET.get('fecha', '')
    if estado_f:
        pedidos = pedidos.filter(estado=estado_f)
    if fecha_f:
        try:
            d = date_type.fromisoformat(fecha_f)
            pedidos = pedidos.filter(fecha_pedido__date=d)
        except ValueError:
            pass

    paginator = Paginator(pedidos, 20)
    page      = paginator.get_page(request.GET.get('pagina', 1))

    return render(request, 'app_docente/historial.html', _ctx(docente, {
        'docente':  docente,
        'page':     page,
        'pedidos':  page,           # alias para compatibilidad con templates existentes
        'estado_f': estado_f,
        'fecha_f':  fecha_f,
    }))


@docente_required
def exportar_csv(request):
    docente = _get_docente(request)
    pedidos = PedidoDocente.objects.filter(docente=docente, estado='entregado').prefetch_related('detalles__producto')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="historial_docente.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Ticket', 'Fecha', 'Estado', 'Tipo Pago', 'Total'])
    for p in pedidos:
        writer.writerow([p.ticket, p.fecha_pedido.strftime('%d/%m/%Y %H:%M'), p.get_estado_display(), p.get_tipo_pago_display(), p.total])
    return response


# ══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def estadisticas(request):
    docente = _get_docente(request)
    ahora = timezone.now()

    from django.db.models.functions import TruncMonth
    from datetime import timedelta

    hace_6_meses = (ahora - timedelta(days=180)).date()

    # Gasto por mes (últimos 6) — una sola query con TruncMonth
    rows_mes = {
        row['mes']: float(row['t'] or 0)
        for row in PedidoDocente.objects.filter(
            docente=docente, estado='entregado',
            fecha_pedido__date__gte=hace_6_meses,
        ).annotate(mes=TruncMonth('fecha_pedido')).values('mes').annotate(t=Sum('total'))
    }
    gasto_meses = []
    for i in range(5, -1, -1):
        months_total = ahora.year * 12 + ahora.month - 1 - i
        mes_dt = ahora.replace(year=months_total // 12, month=months_total % 12 + 1, day=1)
        from django.utils.timezone import make_aware
        import datetime
        try:
            mes_key = make_aware(datetime.datetime(mes_dt.year, mes_dt.month, 1))
        except Exception:
            mes_key = datetime.datetime(mes_dt.year, mes_dt.month, 1)
        gasto_meses.append({'mes': mes_dt.strftime('%b %Y'), 'total': rows_mes.get(mes_key, 0)})

    # Top 5 productos — ya era una sola query con annotate, solo limpiar
    top_prods_data = list(DetallePedidoDocente.objects.filter(
        pedido__docente=docente, pedido__estado='entregado'
    ).values('producto__nombre', 'producto__pk').annotate(
        total_cant=Sum('cantidad')
    ).order_by('-total_cant')[:5])

    # Distribución por categoría — una sola query con values/annotate
    cat_data = [
        {'nombre': row['cat'], 'total': float(row['t'] or 0)}
        for row in DetallePedidoDocente.objects.filter(
            pedido__docente=docente, pedido__estado='entregado'
        ).values(cat=F('producto__categoria__nombre')).annotate(
            t=Sum(F('cantidad') * F('precio_unitario'))
        ).order_by('-t')
        if row['t']
    ]

    # Resumen fiado — una sola query de agregación
    agg_res = PedidoDocente.objects.filter(docente=docente, estado='entregado').aggregate(
        total_gastado=Sum('total')
    )
    resumen = {
        'saldo':         docente.saldo,
        'limite_fiado':  docente.limite_fiado,
        'deuda_fiado':   docente.deuda_fiado,
        'credito_disp':  docente.credito_disponible,
        'total_gastado': agg_res['total_gastado'] or 0,
        'total_pedidos': PedidoDocente.objects.filter(docente=docente).count(),
    }

    return render(request, 'app_docente/estadisticas.html', _ctx(docente, {
        'docente':       docente,
        'gasto_meses':   json.dumps(gasto_meses),
        'top_prods':     top_prods_data,
        'cat_data':      json.dumps(cat_data),
        'resumen':       resumen,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# FAVORITOS
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def favoritos(request):
    docente = _get_docente(request)
    favs = FavoritoDocente.objects.filter(docente=docente).select_related('producto__categoria')
    return render(request, 'app_docente/favoritos.html', _ctx(docente, {
        'docente':   docente,
        'favoritos': favs,
    }))


@docente_required
@require_POST
def toggle_favorito(request, pk):
    docente = _get_docente(request)
    producto = get_object_or_404(Producto, pk=pk)
    fav, created = FavoritoDocente.objects.get_or_create(docente=docente, producto=producto)
    if not created:
        fav.delete()
        return JsonResponse({'estado': 'eliminado'})
    return JsonResponse({'estado': 'agregado'})


# ══════════════════════════════════════════════════════════════════════════════
# RESEÑAS
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
@require_POST
def guardar_reseña(request, pk):
    docente  = _get_docente(request)
    producto = get_object_or_404(Producto, pk=pk)
    calificacion = int(request.POST.get('calificacion', 5))
    comentario   = request.POST.get('comentario', '').strip()[:500]

    ReseñaProducto.objects.update_or_create(
        docente=docente, producto=producto,
        defaults={'calificacion': calificacion, 'comentario': comentario},
    )
    messages.success(request, f'Reseña de "{producto.nombre}" guardada.')
    next_url = request.POST.get('next', 'app_docente:menu')
    return redirect(next_url)


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def perfil(request):
    docente = _get_docente(request)
    user    = request.user

    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name).strip()
        user.last_name  = request.POST.get('last_name', user.last_name).strip()
        user.email      = request.POST.get('email', user.email).strip()
        user.save(update_fields=['first_name', 'last_name', 'email'])

        docente.documento = request.POST.get('documento', docente.documento).strip()
        docente.materia   = request.POST.get('materia', docente.materia).strip()
        docente.perfil.telefono = request.POST.get('telefono', docente.perfil.telefono).strip()
        docente.perfil.save(update_fields=['telefono'])
        docente.save(update_fields=['documento', 'materia'])

        # Cambio de contraseña
        p1 = request.POST.get('password1', '')
        p2 = request.POST.get('password2', '')
        if p1:
            if p1 != p2:
                messages.error(request, 'Las contraseñas no coinciden.')
            elif len(p1) < 8:
                messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            else:
                user.set_password(p1)
                user.save(update_fields=['password'])
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                messages.success(request, 'Contraseña actualizada.')

        messages.success(request, 'Perfil actualizado.')
        return redirect('app_docente:perfil')

    return render(request, 'app_docente/perfil.html', _ctx(docente, {
        'docente': docente,
        'user':    user,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# RECARGA DE SALDO
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def recargar_saldo(request):
    docente = _get_docente(request)
    if request.method == 'POST':
        monto_raw    = request.POST.get('monto', '').strip()
        nota         = request.POST.get('nota', '').strip()[:300]
        comprobante  = request.FILES.get('comprobante')

        try:
            monto = Decimal(monto_raw)
            if monto < 1000:
                raise ValueError('Mínimo $1.000')
        except Exception:
            messages.error(request, 'Monto inválido. El mínimo es $1.000.')
            return redirect('app_docente:recargar_saldo')

        RecargaDocente.objects.create(
            docente=docente,
            monto=monto,
            comprobante=comprobante,
            nota=nota,
        )
        messages.success(request, 'Solicitud de recarga enviada. Un administrador la revisará pronto.')
        return redirect('app_docente:recargar_saldo')

    historial = RecargaDocente.objects.filter(docente=docente)[:20]
    return render(request, 'app_docente/recargar_saldo.html', _ctx(docente, {
        'docente':  docente,
        'historial': historial,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# API NOTIFICACIONES
# ══════════════════════════════════════════════════════════════════════════════

@docente_required
def api_notificaciones(request):
    docente = _get_docente(request)
    notifs = NotificacionDocente.objects.filter(docente=docente, leida=False).order_by('-fecha')[:10]
    data = [{'titulo': n.titulo, 'mensaje': n.mensaje, 'fecha': n.fecha.isoformat()} for n in notifs]
    notifs.update(leida=True)
    return JsonResponse({'notificaciones': data, 'total': len(data)})
