import json
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from authentication.models import Perfil, Estudiante
from app_admin.models import Producto, Categoria, Pedido, DetallePedido
from app_padre.models import RestriccionAlimento, LimiteGasto, Notificacion, AlergiaEstudiante, HorarioCompra

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def estudiante_required(view_func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        try:
            if request.user.perfil.rol != 'estudiante':
                messages.error(request, 'Acceso restringido a estudiantes.')
                return redirect('authentication:login')
        except Perfil.DoesNotExist:
            return redirect('authentication:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _get_estudiante(request):
    return get_object_or_404(Estudiante, perfil=request.user.perfil)


def _get_restricciones(estudiante):
    """Retorna sets de IDs de productos y categorías restringidas para el estudiante."""
    if not estudiante.padre:
        return set(), set()
    base_q = Q(activo=True) & (
        Q(estudiante=estudiante) | Q(estudiante__isnull=True, padre=estudiante.padre)
    )
    prod_ids = set(
        RestriccionAlimento.objects.filter(base_q, producto__isnull=False)
        .values_list('producto_id', flat=True)
    )
    cat_ids = set(
        RestriccionAlimento.objects.filter(base_q, categoria__isnull=False)
        .values_list('categoria_id', flat=True)
    )
    # Restricción automática: productos con ingredientes que contienen alérgenos del estudiante
    alergeno_ids = set(
        AlergiaEstudiante.objects.filter(
            estudiante=estudiante, activo=True, alergeno__isnull=False
        ).values_list('alergeno_id', flat=True)
    )
    if alergeno_ids:
        prod_ids |= set(
            Producto.objects.filter(
                receta__ingrediente__alergenos__in=alergeno_ids
            ).values_list('pk', flat=True)
        )
    return prod_ids, cat_ids


def _get_limites(estudiante):
    """Retorna los límites activos del estudiante."""
    if not estudiante.padre:
        return []
    return list(LimiteGasto.objects.filter(
        padre=estudiante.padre, estudiante=estudiante, activo=True
    ))


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def dashboard(request):
    estudiante = _get_estudiante(request)
    ahora = timezone.now()

    pedidos_recientes = (
        Pedido.objects.filter(estudiante=estudiante)
        .prefetch_related('detalles__producto')
        .order_by('-fecha_pedido')[:5]
    )

    gasto_mes = Pedido.objects.filter(
        estudiante=estudiante, estado='entregado',
        fecha_pedido__month=ahora.month, fecha_pedido__year=ahora.year,
    ).aggregate(t=Sum('total'))['t'] or 0

    gasto_hoy = Pedido.objects.filter(
        estudiante=estudiante, estado='entregado',
        fecha_pedido__date=ahora.date(),
    ).aggregate(t=Sum('total'))['t'] or 0

    n_pedidos = Pedido.objects.filter(estudiante=estudiante).count()

    pedido_activo = Pedido.objects.filter(
        estudiante=estudiante, estado__in=['pendiente', 'preparando', 'listo']
    ).order_by('-fecha_pedido').first()

    limites_data = []
    for lim in _get_limites(estudiante):
        limites_data.append({
            'limite': lim,
            'gasto': lim.gasto_actual(),
            'pct': lim.porcentaje_uso,
            'disponible': lim.disponible,
        })

    # Top 4 productos más pedidos por el estudiante
    top_prods = (
        DetallePedido.objects.filter(
            pedido__estudiante=estudiante, pedido__estado='entregado'
        )
        .values('producto__id', 'producto__nombre', 'producto__precio_venta',
                'producto__disponible', 'producto__categoria__nombre')
        .annotate(veces=Sum('cantidad'))
        .order_by('-veces')[:4]
    )

    return render(request, 'app_estudiante/dashboard.html', {
        'estudiante': estudiante,
        'pedidos_recientes': pedidos_recientes,
        'gasto_mes': gasto_mes,
        'gasto_hoy': gasto_hoy,
        'n_pedidos': n_pedidos,
        'pedido_activo': pedido_activo,
        'limites_data': limites_data,
        'top_prods': top_prods,
    })


# ══════════════════════════════════════════════════════════════════════════════
# MENU + REALIZAR PEDIDO
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def menu(request):
    estudiante = _get_estudiante(request)
    restricciones_prod, restricciones_cat = _get_restricciones(estudiante)

    if request.method == 'POST':
        nota_ped = request.POST.get('nota', '').strip()
        carrito = {}
        for key, val in request.POST.items():
            if key.startswith('qty_'):
                try:
                    prod_id = int(key[4:])
                    qty = int(val)
                    if qty > 0:
                        carrito[prod_id] = qty
                except (ValueError, TypeError):
                    pass

        if not carrito:
            messages.error(request, 'El carrito esta vacio.')
            return redirect('app_estudiante:menu')

        # Validar horario de compra asignado por el padre
        if estudiante.padre:
            horarios_activos = HorarioCompra.objects.filter(estudiante=estudiante, activo=True)
            if horarios_activos.exists():
                ahora_hora = timezone.localtime().time()
                en_horario = any(h.hora_inicio <= ahora_hora <= h.hora_fin for h in horarios_activos)
                if not en_horario:
                    messages.error(request, 'No es un horario permitido para realizar pedidos.')
                    return redirect('app_estudiante:menu')

        total = Decimal('0')
        lineas = []
        for prod_id, qty in carrito.items():
            try:
                prod = Producto.objects.get(pk=prod_id, disponible=True)
            except Producto.DoesNotExist:
                messages.error(request, 'Uno de los productos ya no esta disponible.')
                return redirect('app_estudiante:menu')

            if prod.id in restricciones_prod or prod.categoria_id in restricciones_cat:
                messages.error(request, f'"{prod.nombre}" esta restringido por tu acudiente.')
                return redirect('app_estudiante:menu')

            if prod.tipo == 'simple' and prod.stock < qty:
                messages.error(
                    request,
                    f'Stock insuficiente para "{prod.nombre}" (disponible: {prod.stock}).'
                )
                return redirect('app_estudiante:menu')

            subtotal = Decimal(str(prod.precio_venta)) * qty
            total += subtotal
            lineas.append((prod, qty, subtotal))

        # Crear pedido dentro de transacción atómica con lock
        try:
            with transaction.atomic():
                # Lock del registro del estudiante para evitar race conditions
                est_locked = Estudiante.objects.select_for_update().get(pk=estudiante.pk)

                # Verificar saldo con datos frescos (después del lock)
                if est_locked.saldo < total:
                    messages.error(
                        request,
                        f'Saldo insuficiente. Disponible: ${est_locked.saldo:,.0f}, pedido: ${total:,.0f}.'
                    )
                    return redirect('app_estudiante:menu')

                # Verificar limites de gasto dentro de la transacción
                for lim in _get_limites(est_locked):
                    if float(lim.gasto_actual()) + float(total) > float(lim.monto):
                        messages.error(
                            request,
                            f'El pedido supera tu límite {lim.get_tipo_display().lower()} de ${lim.monto:,.0f}.'
                        )
                        return redirect('app_estudiante:menu')

                # Crear pedido con totales iniciales en 0 (se recalculan después)
                pedido = Pedido.objects.create(
                    estudiante=est_locked,
                    total=0,  # Se recalcula
                    costo_total=0,  # Se recalcula
                    nota=nota_ped
                )
                # Crear detalles con costos correctos
                for prod, qty, _ in lineas:
                    DetallePedido.objects.create(
                        pedido=pedido, producto=prod,
                        cantidad=qty, precio_unitario=prod.precio_venta,
                        costo_unitario=prod.costo_calculado,
                    )
                # Recalcular totales desde detalles
                pedido.recalcular_totales()

                # Descontar saldo
                est_locked.saldo -= total
                est_locked.save(update_fields=['saldo'])
                # Actualizar referencia local
                estudiante.saldo = est_locked.saldo
        except Exception:
            logger.exception('Error al procesar pedido de estudiante')
            messages.error(request, 'Error al procesar el pedido. Intenta de nuevo.')
            return redirect('app_estudiante:menu')

        messages.success(request, f'Pedido {pedido.ticket} realizado por ${total:,.0f}.')
        return redirect('app_estudiante:historial')

    # GET — Mostrar menu
    cat_slug = request.GET.get('cat', '')
    q = request.GET.get('q', '').strip()

    productos_qs = (
        Producto.objects.filter(disponible=True, stock__gt=0)
        .select_related('categoria')
        .order_by('categoria__nombre', 'nombre')
    )
    if cat_slug:
        productos_qs = productos_qs.filter(categoria__nombre=cat_slug)
    if q:
        productos_qs = productos_qs.filter(nombre__icontains=q)

    categorias = Categoria.objects.filter(activa=True)
    prods_lista = [
        (p, p.id in restricciones_prod or p.categoria_id in restricciones_cat)
        for p in productos_qs
    ]

    # Determinar si el estudiante está dentro de su horario permitido
    fuera_de_horario = False
    if estudiante.padre:
        horarios_activos = HorarioCompra.objects.filter(estudiante=estudiante, activo=True)
        if horarios_activos.exists():
            ahora_hora = timezone.localtime().time()
            fuera_de_horario = not any(h.hora_inicio <= ahora_hora <= h.hora_fin for h in horarios_activos)

    return render(request, 'app_estudiante/menu.html', {
        'estudiante': estudiante,
        'prods_lista': prods_lista,
        'categorias': categorias,
        'cat_activa': cat_slug,
        'q': q,
        'restricciones_prod': restricciones_prod,
        'restricciones_cat': restricciones_cat,
        'fuera_de_horario': fuera_de_horario,
    })


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL DE PEDIDOS
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def historial(request):
    estudiante = _get_estudiante(request)
    estado  = request.GET.get('estado', '')
    fecha_d = request.GET.get('desde', '')
    fecha_h = request.GET.get('hasta', '')

    pedidos = (
        Pedido.objects.filter(estudiante=estudiante)
        .prefetch_related('detalles__producto')
        .order_by('-fecha_pedido')
    )

    if estado:
        pedidos = pedidos.filter(estado=estado)
    if fecha_d:
        pedidos = pedidos.filter(fecha_pedido__date__gte=fecha_d)
    if fecha_h:
        pedidos = pedidos.filter(fecha_pedido__date__lte=fecha_h)

    gasto_total = pedidos.filter(estado='entregado').aggregate(t=Sum('total'))['t'] or 0
    n_pedidos   = pedidos.count()

    return render(request, 'app_estudiante/historial.html', {
        'estudiante': estudiante,
        'pedidos': pedidos[:80],
        'estado_activo': estado,
        'fecha_desde': fecha_d,
        'fecha_hasta': fecha_h,
        'gasto_total': gasto_total,
        'n_pedidos': n_pedidos,
        'ESTADO_CHOICES': Pedido.ESTADO_CHOICES,
    })


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def perfil(request):
    estudiante = _get_estudiante(request)

    if request.method == 'POST':
        user = request.user
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name',  '').strip()
        email      = request.POST.get('email',      '').strip()
        telefono   = request.POST.get('telefono',   '').strip()
        password1  = request.POST.get('password1',  '')
        password2  = request.POST.get('password2',  '')

        if not first_name or not last_name:
            messages.error(request, 'Nombre y apellido son obligatorios.')
            return redirect('app_estudiante:perfil')

        user.first_name = first_name
        user.last_name  = last_name
        user.email      = email
        user.save(update_fields=['first_name', 'last_name', 'email'])

        perfil_obj = user.perfil
        perfil_obj.telefono = telefono
        perfil_obj.save(update_fields=['telefono'])

        if password1:
            password_actual = request.POST.get('password_actual', '')
            if not user.check_password(password_actual):
                messages.error(request, 'La contrasena actual es incorrecta.')
                return redirect('app_estudiante:perfil')
            if password1 != password2:
                messages.error(request, 'Las contrasenas nuevas no coinciden.')
                return redirect('app_estudiante:perfil')
            if len(password1) < 8:
                messages.error(request, 'La contrasena debe tener minimo 8 caracteres.')
                return redirect('app_estudiante:perfil')
            user.set_password(password1)
            user.save()
            messages.success(request, 'Contrasena actualizada. Inicia sesion nuevamente.')
            return redirect('authentication:login')

        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('app_estudiante:perfil')

    limites_data = []
    for lim in _get_limites(estudiante):
        limites_data.append({
            'limite': lim,
            'gasto': lim.gasto_actual(),
            'pct': lim.porcentaje_uso,
            'disponible': lim.disponible,
        })

    return render(request, 'app_estudiante/perfil.html', {
        'estudiante': estudiante,
        'limites_data': limites_data,
    })


# ══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS PERSONALES
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def estadisticas(request):
    estudiante = _get_estudiante(request)
    ahora = timezone.now()

    # Gastos por día — últimos 30 días
    hace_30 = ahora - timezone.timedelta(days=30)
    gastos_dia = (
        Pedido.objects.filter(
            estudiante=estudiante, estado='entregado',
            fecha_pedido__gte=hace_30,
        )
        .annotate(dia=TruncDate('fecha_pedido'))
        .values('dia')
        .annotate(total=Sum('total'))
        .order_by('dia')
    )

    # Gastos por mes — últimos 6 meses
    hace_180 = ahora - timezone.timedelta(days=180)
    gastos_mes = (
        Pedido.objects.filter(
            estudiante=estudiante, estado='entregado',
            fecha_pedido__gte=hace_180,
        )
        .annotate(mes=TruncMonth('fecha_pedido'))
        .values('mes')
        .annotate(total=Sum('total'))
        .order_by('mes')
    )

    # Top 6 productos más pedidos
    top_productos = (
        DetallePedido.objects.filter(
            pedido__estudiante=estudiante, pedido__estado='entregado'
        )
        .values('producto__nombre')
        .annotate(veces=Sum('cantidad'))
        .order_by('-veces')[:6]
    )

    # KPIs
    gasto_total = Pedido.objects.filter(
        estudiante=estudiante, estado='entregado'
    ).aggregate(t=Sum('total'))['t'] or 0

    n_entregados = Pedido.objects.filter(
        estudiante=estudiante, estado='entregado'
    ).count()

    n_cancelados = Pedido.objects.filter(
        estudiante=estudiante, estado='cancelado'
    ).count()

    promedio = round(float(gasto_total) / n_entregados, 0) if n_entregados else 0

    producto_fav = top_productos[0]['producto__nombre'] if top_productos else '—'

    # Serializar para Chart.js
    dias_labels = [str(g['dia']) for g in gastos_dia]
    dias_data   = [float(g['total']) for g in gastos_dia]

    meses_labels = [g['mes'].strftime('%b %Y') for g in gastos_mes]
    meses_data   = [float(g['total']) for g in gastos_mes]

    prods_labels = [p['producto__nombre'] for p in top_productos]
    prods_data   = [int(p['veces']) for p in top_productos]

    return render(request, 'app_estudiante/estadisticas.html', {
        'estudiante':     estudiante,
        'gasto_total':    gasto_total,
        'n_entregados':   n_entregados,
        'n_cancelados':   n_cancelados,
        'promedio':       promedio,
        'producto_fav':   producto_fav,
        'top_productos':  top_productos,
        'dias_labels':    json.dumps(dias_labels),
        'dias_data':      json.dumps(dias_data),
        'meses_labels':   json.dumps(meses_labels),
        'meses_data':     json.dumps(meses_data),
        'prods_labels':   json.dumps(prods_labels),
        'prods_data':     json.dumps(prods_data),
    })


# ══════════════════════════════════════════════════════════════════════════════
# CANCELAR PEDIDO
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def cancelar_pedido(request, pk):
    if request.method != 'POST':
        return redirect('app_estudiante:historial')

    estudiante = _get_estudiante(request)
    pedido = get_object_or_404(Pedido, pk=pk, estudiante=estudiante)

    if pedido.estado != 'pendiente':
        messages.error(request, 'Solo puedes cancelar pedidos en estado Pendiente.')
        return redirect('app_estudiante:historial')

    # Devolver saldo y cancelar pedido en una sola transacción atómica
    with transaction.atomic():
        est_locked = Estudiante.objects.select_for_update().get(pk=estudiante.pk)
        pedido_locked = Pedido.objects.select_for_update().get(pk=pedido.pk)

        # Re-verificar estado (evita doble cancelación por race condition)
        if pedido_locked.estado != 'pendiente':
            messages.error(request, 'Este pedido ya no está en estado Pendiente.')
            return redirect('app_estudiante:historial')

        pedido_locked.estado = 'cancelado'
        pedido_locked.save(update_fields=['estado'])

        est_locked.saldo += pedido_locked.total
        est_locked.save(update_fields=['saldo'])
        estudiante.saldo = est_locked.saldo

    messages.success(
        request,
        f'Pedido {pedido.ticket} cancelado. Se devolvieron ${pedido.total:,.0f} a tu saldo.'
    )
    return redirect('app_estudiante:historial')


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICACIONES DEL ESTUDIANTE (recibe de su padre)
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def notificaciones(request):
    estudiante = _get_estudiante(request)
    notifs = []
    if estudiante.padre:
        notifs = Notificacion.objects.filter(padre=estudiante.padre).order_by('-fecha')[:50]
    return render(request, 'app_estudiante/notificaciones.html', {
        'estudiante': estudiante,
        'notificaciones': notifs,
    })


# ══════════════════════════════════════════════════════════════════════════════
# MIS RESTRICCIONES Y ALERGIAS (solo lectura para el estudiante)
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def mis_restricciones(request):
    estudiante = _get_estudiante(request)
    restricciones_prod_ids, restricciones_cat_ids = _get_restricciones(estudiante)

    prods_rest = Producto.objects.filter(pk__in=restricciones_prod_ids).select_related('categoria')
    cats_rest  = Categoria.objects.filter(pk__in=restricciones_cat_ids)

    alergias = []
    if estudiante.padre:
        alergias = AlergiaEstudiante.objects.filter(
            estudiante=estudiante, activo=True
        ).order_by('-gravedad', 'nombre')

    return render(request, 'app_estudiante/mis_restricciones.html', {
        'estudiante': estudiante,
        'prods_rest': prods_rest,
        'cats_rest': cats_rest,
        'alergias': alergias,
    })


# ══════════════════════════════════════════════════════════════════════════════
# SALDO — detalle de movimientos del estudiante
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def mi_saldo(request):
    estudiante = _get_estudiante(request)
    ahora      = timezone.now()

    from app_padre.models import RecargaSaldo
    from app_estudiante.models import RecargaEstudiante

    recargas_padre = RecargaSaldo.objects.filter(
        estudiante=estudiante
    ).order_by('-fecha')[:20]

    recargas_propias = RecargaEstudiante.objects.filter(
        estudiante=estudiante
    ).order_by('-fecha')[:20]

    pedidos_recientes = Pedido.objects.filter(
        estudiante=estudiante, estado__in=['pendiente', 'preparando', 'listo', 'entregado']
    ).order_by('-fecha_pedido')[:20]

    gasto_mes = Pedido.objects.filter(
        estudiante=estudiante, estado='entregado',
        fecha_pedido__month=ahora.month, fecha_pedido__year=ahora.year,
    ).aggregate(t=Sum('total'))['t'] or 0

    recargado_padre_mes = RecargaSaldo.objects.filter(
        estudiante=estudiante, estado='aprobada',
        fecha__month=ahora.month, fecha__year=ahora.year,
    ).aggregate(t=Sum('monto'))['t'] or 0

    recargado_propio_mes = RecargaEstudiante.objects.filter(
        estudiante=estudiante, estado='aprobada',
        fecha__month=ahora.month, fecha__year=ahora.year,
    ).aggregate(t=Sum('monto'))['t'] or 0

    recargado_mes = (recargado_padre_mes or 0) + (recargado_propio_mes or 0)

    limites_data = []
    for lim in _get_limites(estudiante):
        limites_data.append({
            'limite': lim,
            'gasto': lim.gasto_actual(),
            'pct': lim.porcentaje_uso,
            'disponible': lim.disponible,
        })

    return render(request, 'app_estudiante/mi_saldo.html', {
        'estudiante':        estudiante,
        'recargas_padre':    recargas_padre,
        'recargas_propias':  recargas_propias,
        'pedidos_recientes': pedidos_recientes,
        'gasto_mes':         gasto_mes,
        'recargado_mes':     recargado_mes,
        'limites_data':      limites_data,
    })


# ══════════════════════════════════════════════════════════════════════════════
# MI QR (carnet digital del estudiante)
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
# ══════════════════════════════════════════════════════════════════════════════
# MI QR (carnet digital del estudiante)
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def mi_qr(request):
    import qrcode, io, base64
    estudiante = _get_estudiante(request)

    # Generar QR en el servidor → imagen PNG en base64
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(str(estudiante.codigo))
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f0f0e", back_color="#ffffff")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render(request, 'app_estudiante/mi_qr.html', {
        'estudiante': estudiante,
        'qr_data':    str(estudiante.codigo),   # por si aún lo necesitas
        'qr_img_b64': qr_b64,
    })

# ══════════════════════════════════════════════════════════════════════════════
# RECARGAR SALDO AUTÓNOMO (MP directo del estudiante)
# ══════════════════════════════════════════════════════════════════════════════

@estudiante_required
def recargar_saldo(request):
    from app_estudiante.models import RecargaEstudiante

    estudiante = _get_estudiante(request)

    if not estudiante.puede_recargar_autonomo:
        messages.error(request, 'Tu acudiente no ha habilitado las recargas autónomas. Pídele que lo active desde su panel.')
        return redirect('app_estudiante:mi_saldo')

    if request.method == 'POST':
        try:
            monto = float(request.POST.get('monto', 0))
            nota  = request.POST.get('nota', '').strip()
        except (ValueError, TypeError):
            messages.error(request, 'Monto inválido.')
            return redirect('app_estudiante:recargar_saldo')

        if monto < 1000:
            messages.error(request, 'El monto mínimo es $1.000.')
        elif monto > 2_000_000:
            messages.error(request, 'El monto máximo por recarga es $2.000.000.')
        else:
            RecargaEstudiante.objects.filter(
                estudiante=estudiante, estado='pendiente',
                mp_preference_id__gt='', mp_payment_id='',
            ).update(estado='rechazada', nota_admin='Cancelada al iniciar nueva recarga', fecha_resolucion=timezone.now())

            recarga = RecargaEstudiante.objects.create(
                estudiante=estudiante,
                monto=monto, nota=nota, estado='pendiente',
            )
            try:
                from pagos.utils import crear_preferencia_mp
                nombre = estudiante.perfil.user.get_full_name() or estudiante.codigo
                pref = crear_preferencia_mp(
                    titulo=f'Recarga Punto Asis — {nombre}',
                    monto=monto,
                    external_reference=f'est-{recarga.pk}',
                )
                recarga.mp_preference_id = pref['id']
                recarga.save(update_fields=['mp_preference_id'])
                return redirect(pref['init_point'])
            except Exception:
                logger.exception('Error al crear preferencia MercadoPago (estudiante)')
                recarga.delete()
                messages.error(request, 'No se pudo conectar con MercadoPago. Intenta de nuevo.')
                return redirect('app_estudiante:recargar_saldo')

    historial = RecargaEstudiante.objects.filter(estudiante=estudiante).order_by('-fecha')[:15]
    return render(request, 'app_estudiante/recargar_saldo.html', {
        'estudiante': estudiante,
        'historial':  historial,
    })
