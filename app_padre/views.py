import json
import csv
import io
from decimal import Decimal
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Avg, Q, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from authentication.models import Perfil, Padre, Estudiante
from authentication.utils import generar_username as _generar_username
from app_admin.models import Producto, Categoria, Pedido, DetallePedido
from .models import (
    RecargaSaldo, LimiteGasto, RestriccionAlimento,
    Notificacion, HorarioCompra, PedidoPadre,
    PedidoProgramado, DetalleProgramado,
    AlergiaEstudiante,
)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def padre_required(view_func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        try:
            if request.user.perfil.rol != 'padre':
                messages.error(request, 'Acceso restringido a padres de familia.')
                return redirect('authentication:login')
        except Perfil.DoesNotExist:
            return redirect('authentication:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _get_padre(request):
    return get_object_or_404(Padre, perfil=request.user.perfil)



def _n_notif(padre):
    return Notificacion.objects.filter(padre=padre, leida=False).count()


def _ctx_padre(padre, extra=None):
    """Contexto base para todas las vistas del padre.
    Inyecta hijo_sidebar_pk (pk del primer hijo) para el sidebar."""
    primer_hijo = padre.hijos.order_by('perfil__user__first_name').first()
    ctx = {
        'hijo_sidebar_pk': primer_hijo.pk if primer_hijo else None,
    }
    if extra:
        ctx.update(extra)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def dashboard(request):
    padre = _get_padre(request)
    hijos = padre.hijos.select_related('perfil__user').order_by('perfil__user__first_name')

    ahora = timezone.now()
    saldo_total = hijos.aggregate(total=Sum('saldo'))['total'] or 0

    gasto_mes = Pedido.objects.filter(
        estudiante__padre=padre, estado='entregado',
        fecha_pedido__month=ahora.month, fecha_pedido__year=ahora.year,
    ).aggregate(t=Sum('total'))['t'] or 0

    gasto_semana = Pedido.objects.filter(
        estudiante__padre=padre, estado='entregado',
        fecha_pedido__gte=ahora - timezone.timedelta(days=7),
    ).aggregate(t=Sum('total'))['t'] or 0

    pedidos_recientes = Pedido.objects.filter(
        estudiante__padre=padre
    ).select_related('estudiante__perfil__user').prefetch_related('pedido_padre').order_by('-fecha_pedido')[:8]

    recargas_pendientes = RecargaSaldo.objects.filter(padre=padre, estado='pendiente').count()

    # Límites cerca del tope
    alertas_limites = []
    for limite in LimiteGasto.objects.filter(padre=padre, activo=True).select_related('estudiante__perfil__user'):
        pct = limite.porcentaje_uso
        if pct >= 80:
            alertas_limites.append({'limite': limite, 'pct': pct})

    # Últimas notificaciones no leídas
    notificaciones_recientes = Notificacion.objects.filter(padre=padre).order_by('-fecha')[:5]
    n_notif = Notificacion.objects.filter(padre=padre, leida=False).count()

    # Hijos con saldo bajo (< 5000)
    hijos_saldo_bajo = hijos.filter(saldo__lt=5000)

    # Chart: gastos últimos 7 días por hijo
    labels_7d = []
    for i in range(6, -1, -1):
        d = (ahora - timezone.timedelta(days=i)).date()
        labels_7d.append(d.strftime('%d/%m'))

    return render(request, 'app_padre/dashboard.html', _ctx_padre(padre, {
        'padre': padre,
        'hijos': hijos,
        'n_hijos': hijos.count(),
        'saldo_total': saldo_total,
        'gasto_mes': gasto_mes,
        'gasto_semana': gasto_semana,
        'pedidos_recientes': pedidos_recientes,
        'recargas_pendientes': recargas_pendientes,
        'alertas_limites': alertas_limites,
        'notificaciones_recientes': notificaciones_recientes,
        'n_notif': n_notif,
        'hijos_saldo_bajo': hijos_saldo_bajo,
        'labels_7d': json.dumps(labels_7d),
    }))


# ══════════════════════════════════════════════════════════════════════════════
# MIS HIJOS
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def hijos(request):
    padre = _get_padre(request)
    hijos_qs = padre.hijos.select_related('perfil__user').order_by('perfil__user__first_name')

    hijos_data = []
    for hijo in hijos_qs:
        ultimas_recargas = RecargaSaldo.objects.filter(estudiante=hijo).order_by('-fecha')[:3]
        ultimos_pedidos  = Pedido.objects.filter(estudiante=hijo).order_by('-fecha_pedido')[:3]
        limites          = LimiteGasto.objects.filter(estudiante=hijo, activo=True)
        n_restricciones  = RestriccionAlimento.objects.filter(
            Q(estudiante=hijo) | Q(estudiante__isnull=True, padre=padre), activo=True
        ).count()
        gasto_hoy = Pedido.objects.filter(
            estudiante=hijo, estado='entregado',
            fecha_pedido__date=timezone.now().date(),
        ).aggregate(t=Sum('total'))['t'] or 0
        hijos_data.append({
            'hijo': hijo,
            'recargas': ultimas_recargas,
            'pedidos': ultimos_pedidos,
            'limites': limites,
            'n_restricciones': n_restricciones,
            'gasto_hoy': gasto_hoy,
        })

    return render(request, 'app_padre/hijos.html', _ctx_padre(padre, {
        'padre': padre,
        'hijos_data': hijos_data,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# CREAR ESTUDIANTE
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def crear_estudiante(request):
    padre = _get_padre(request)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name',  '').strip()
        password1  = request.POST.get('password1',  '')
        password2  = request.POST.get('password2',  '')
        grado      = request.POST.get('grado',      '').strip()
        codigo     = request.POST.get('codigo',     '').strip()

        errores = []
        if not all([first_name, last_name, password1, grado, codigo]):
            errores.append('Todos los campos son obligatorios.')
        if password1 != password2:
            errores.append('Las contraseñas no coinciden.')
        if len(password1) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if Estudiante.objects.filter(codigo=codigo).exists():
            errores.append('Ya existe un estudiante con ese código.')

        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, 'app_padre/crear_estudiante.html', _ctx_padre(padre, {
                'padre': padre, 'form_data': request.POST,
            }))

        username = _generar_username(first_name, last_name)
        user = User.objects.create_user(
            username=username, password=password1,
            first_name=first_name, last_name=last_name,
        )
        perfil = Perfil.objects.create(user=user, rol='estudiante')
        Estudiante.objects.create(perfil=perfil, padre=padre, grado=grado, codigo=codigo, saldo=0)
        messages.success(request, f'Cuenta de {first_name} {last_name} creada exitosamente.')
        return redirect('app_padre:hijos')

    return render(request, 'app_padre/crear_estudiante.html', _ctx_padre(padre, {
        'padre': padre,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# RECARGAR SALDO (flujo con comprobante)
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def recargar_saldo(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)

    if request.method == 'POST':
        try:
            monto = float(request.POST.get('monto', 0))
            nota  = request.POST.get('nota', '').strip()
        except (ValueError, TypeError):
            messages.error(request, 'Monto inválido.')
            return redirect('app_padre:recargar_saldo', pk=pk)

        comprobante = request.FILES.get('comprobante')

        if monto <= 0:
            messages.error(request, 'El monto debe ser mayor a cero.')
        elif monto > 2_000_000:
            messages.error(request, 'El monto máximo por recarga es $2.000.000.')
        elif not comprobante:
            messages.error(request, 'Debes adjuntar el comprobante de pago para enviar la solicitud.')
        else:
            recarga = RecargaSaldo.objects.create(
                estudiante=estudiante, padre=padre,
                monto=monto, nota=nota, comprobante=comprobante,
                estado='pendiente',
            )
            Notificacion.objects.create(
                padre=padre,
                tipo='recarga_pendiente',
                titulo='Recarga en revisión',
                mensaje=f'Tu solicitud de recarga de ${monto:,.0f} para {estudiante.perfil.user.get_full_name()} está siendo revisada.',
                url_accion='/padre/hijos/',
            )
            nombre = estudiante.perfil.user.first_name or estudiante.perfil.user.username
            messages.success(request, f'Solicitud de recarga de ${monto:,.0f} enviada. El saldo se actualizará cuando sea aprobada.')
            return redirect('app_padre:hijos')

    historial = RecargaSaldo.objects.filter(estudiante=estudiante).order_by('-fecha')[:15]
    return render(request, 'app_padre/recargar_saldo.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'historial': historial,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# MENÚ (vitrina con restricciones)
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def menu(request):
    padre    = _get_padre(request)
    cat_slug = request.GET.get('cat', '')
    q        = request.GET.get('q', '').strip()
    hijo_pk  = request.GET.get('hijo', '')

    productos = Producto.objects.filter(disponible=True).select_related('categoria').order_by('categoria', 'nombre')

    if cat_slug:
        productos = productos.filter(categoria__nombre=cat_slug)
    if q:
        productos = productos.filter(nombre__icontains=q)

    categorias = Categoria.objects.filter(activa=True)
    hijos      = padre.hijos.select_related('perfil__user')

    # Restricciones del hijo seleccionado
    restricciones_ids_prod = set()
    restricciones_ids_cat  = set()
    hijo_sel = None
    if hijo_pk:
        try:
            hijo_sel = padre.hijos.get(pk=hijo_pk)
            qs_r = RestriccionAlimento.objects.filter(
                Q(estudiante=hijo_sel) | Q(estudiante__isnull=True, padre=padre),
                activo=True,
            )
            restricciones_ids_prod = set(qs_r.filter(producto__isnull=False).values_list('producto_id', flat=True))
            restricciones_ids_cat  = set(qs_r.filter(categoria__isnull=False).values_list('categoria_id', flat=True))
        except Estudiante.DoesNotExist:
            pass

    # Anotar cada producto con su estado de restricción
    productos_list = []
    for p in productos:
        restringido = p.id in restricciones_ids_prod or p.categoria_id in restricciones_ids_cat
        productos_list.append((p, restringido))

    return render(request, 'app_padre/menu.html', _ctx_padre(padre, {
        'padre': padre,
        'productos': [p for p, _ in productos_list],
        'productos_list': productos_list,
        'restricciones_prod': restricciones_ids_prod,
        'restricciones_cat': restricciones_ids_cat,
        'categorias': categorias,
        'cat_activa': cat_slug,
        'q': q,
        'hijos': hijos,
        'hijo_sel': hijo_sel,
        'hijo_pk': hijo_pk,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL DE PEDIDOS
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def historial(request):
    padre   = _get_padre(request)
    hijo_pk = request.GET.get('hijo',   '')
    estado  = request.GET.get('estado', '')
    fecha_d = request.GET.get('desde',  '')
    fecha_h = request.GET.get('hasta',  '')

    hijos_qs = padre.hijos.select_related('perfil__user')

    pedidos = Pedido.objects.filter(
        estudiante__padre=padre
    ).select_related('estudiante__perfil__user').prefetch_related('detalles__producto', 'pedido_padre__padre').order_by('-fecha_pedido')

    if hijo_pk:
        pedidos = pedidos.filter(estudiante__pk=hijo_pk)
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if fecha_d:
        pedidos = pedidos.filter(fecha_pedido__date__gte=fecha_d)
    if fecha_h:
        pedidos = pedidos.filter(fecha_pedido__date__lte=fecha_h)

    from django.core.paginator import Paginator

    gasto_total = pedidos.filter(estado='entregado').aggregate(t=Sum('total'))['t'] or 0
    n_pedidos   = pedidos.count()

    paginator = Paginator(pedidos, 20)
    page      = paginator.get_page(request.GET.get('pagina', 1))

    return render(request, 'app_padre/historial.html', _ctx_padre(padre, {
        'padre':         padre,
        'page':          page,
        'pedidos':       page,   # alias para compatibilidad con templates existentes
        'hijos':         hijos_qs,
        'hijo_activo':   hijo_pk,
        'estado_activo': estado,
        'fecha_desde':   fecha_d,
        'fecha_hasta':   fecha_h,
        'gasto_total':   gasto_total,
        'n_pedidos':     n_pedidos,
        'ESTADO_CHOICES': Pedido.ESTADO_CHOICES,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS Y REPORTES
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def estadisticas(request):
    padre    = _get_padre(request)
    hijo_pk  = request.GET.get('hijo', '')
    periodo  = request.GET.get('periodo', '30')
    ahora    = timezone.now()

    try:
        dias = int(periodo)
    except ValueError:
        dias = 30
    inicio = ahora - timezone.timedelta(days=dias)

    filtro_base = Q(estudiante__padre=padre, estado='entregado', fecha_pedido__gte=inicio)
    if hijo_pk:
        filtro_base &= Q(estudiante__pk=hijo_pk)

    pedidos_qs = Pedido.objects.filter(filtro_base)

    # Gasto total en periodo
    gasto_periodo = pedidos_qs.aggregate(t=Sum('total'))['t'] or 0
    n_pedidos     = pedidos_qs.count()
    ticket_prom   = round(gasto_periodo / n_pedidos, 0) if n_pedidos else 0

    # Gasto por día (últimos N días)
    gasto_diario = defaultdict(float)
    for p in pedidos_qs.values('fecha_pedido', 'total'):
        dia = p['fecha_pedido'].strftime('%d/%m')
        gasto_diario[dia] += float(p['total'])

    labels_dias = []
    data_dias   = []
    for i in range(dias - 1, -1, -1):
        d = (ahora - timezone.timedelta(days=i)).strftime('%d/%m')
        labels_dias.append(d)
        data_dias.append(round(gasto_diario.get(d, 0), 0))

    # Productos más comprados — suma de unidades y pesos (cantidad × precio_unitario = subtotal real)
    top_productos = (
        DetallePedido.objects
        .filter(pedido__in=pedidos_qs)
        .annotate(subtotal_linea=F('cantidad') * F('precio_unitario'))
        .values('producto__nombre')
        .annotate(
            total_uds=Sum('cantidad'),
            total_pesos=Sum('subtotal_linea'),
        )
        .order_by('-total_uds')[:10]
    )
    top_labels = [t['producto__nombre'] for t in top_productos]
    top_data   = [int(t['total_uds']) for t in top_productos]

    # Gasto por categoría — suma correcta de (cantidad × precio_unitario)
    gasto_cat = (
        DetallePedido.objects
        .filter(pedido__in=pedidos_qs)
        .annotate(subtotal_linea=F('cantidad') * F('precio_unitario'))
        .values('producto__categoria__nombre')
        .annotate(total=Sum('subtotal_linea'))
        .order_by('-total')
    )
    cat_labels = [c['producto__categoria__nombre'] or 'Sin categoría' for c in gasto_cat]
    cat_data   = [round(float(c['total'] or 0), 0) for c in gasto_cat]

    # Gasto por hijo en UNA sola query (evita N+1)
    gasto_hijo = []
    if not hijo_pk:
        hijos_gasto = (
            Pedido.objects
            .filter(estudiante__padre=padre, estado='entregado', fecha_pedido__gte=inicio)
            .values('estudiante__pk', 'estudiante__perfil__user__first_name', 'estudiante__perfil__user__last_name')
            .annotate(gasto=Sum('total'))
        )
        for h in hijos_gasto:
            nombre = f"{h['estudiante__perfil__user__first_name']} {h['estudiante__perfil__user__last_name']}".strip()
            gasto_hijo.append({'nombre': nombre or f"Hijo #{h['estudiante__pk']}", 'gasto': float(h['gasto'] or 0)})

    # Comparativa semana actual vs anterior
    ini_sem_actual   = ahora - timezone.timedelta(days=ahora.weekday())
    ini_sem_actual   = ini_sem_actual.replace(hour=0, minute=0, second=0, microsecond=0)
    ini_sem_anterior = ini_sem_actual - timezone.timedelta(weeks=1)

    sem_actual = Pedido.objects.filter(
        Q(estudiante__padre=padre) & (Q(estudiante__pk=hijo_pk) if hijo_pk else Q()),
        estado='entregado', fecha_pedido__gte=ini_sem_actual,
    ).aggregate(t=Sum('total'))['t'] or 0

    sem_anterior = Pedido.objects.filter(
        Q(estudiante__padre=padre) & (Q(estudiante__pk=hijo_pk) if hijo_pk else Q()),
        estado='entregado',
        fecha_pedido__gte=ini_sem_anterior,
        fecha_pedido__lt=ini_sem_actual,
    ).aggregate(t=Sum('total'))['t'] or 0

    hijos = padre.hijos.select_related('perfil__user')

    return render(request, 'app_padre/estadisticas.html', _ctx_padre(padre, {
        'padre': padre,
        'hijos': hijos,
        'hijo_pk': hijo_pk,
        'periodo': str(dias),
        'gasto_periodo': gasto_periodo,
        'n_pedidos': n_pedidos,
        'ticket_prom': ticket_prom,
        'labels_dias': json.dumps(labels_dias),
        'data_dias': json.dumps(data_dias),
        'top_labels': json.dumps(top_labels),
        'top_data': json.dumps(top_data),
        'cat_labels': json.dumps(cat_labels),
        'cat_data': json.dumps(cat_data),
        'gasto_hijo': json.dumps(gasto_hijo),
        'sem_actual': sem_actual,
        'sem_anterior': sem_anterior,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# EXPORTAR HISTORIAL (CSV)
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def exportar_csv(request):
    padre   = _get_padre(request)
    hijo_pk = request.GET.get('hijo', '')
    dias    = int(request.GET.get('dias', 30))
    inicio  = timezone.now() - timezone.timedelta(days=dias)

    pedidos = Pedido.objects.filter(
        estudiante__padre=padre, fecha_pedido__gte=inicio,
    ).select_related('estudiante__perfil__user').prefetch_related('detalles__producto').order_by('-fecha_pedido')
    if hijo_pk:
        pedidos = pedidos.filter(estudiante__pk=hijo_pk)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="historial_pedidos.csv"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)
    writer.writerow(['Ticket', 'Estudiante', 'Fecha', 'Estado', 'Total', 'Productos'])
    for p in pedidos:
        prods = '; '.join([f'{d.cantidad}x {d.producto.nombre}' for d in p.detalles.all()])
        writer.writerow([
            p.ticket,
            p.estudiante.perfil.user.get_full_name(),
            p.fecha_pedido.strftime('%d/%m/%Y %H:%M'),
            p.get_estado_display(),
            f'${p.total:,.0f}',
            prods,
        ])
    return response


# ══════════════════════════════════════════════════════════════════════════════
# LÍMITES DE GASTO
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def limites(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'delete':
            lid = request.POST.get('limite_id')
            LimiteGasto.objects.filter(pk=lid, padre=padre).delete()
            messages.success(request, 'Límite eliminado.')
            return redirect('app_padre:limites', pk=pk)

        if action == 'toggle':
            lid = request.POST.get('limite_id')
            l = get_object_or_404(LimiteGasto, pk=lid, padre=padre)
            l.activo = not l.activo
            l.save(update_fields=['activo'])
            return redirect('app_padre:limites', pk=pk)

        tipo  = request.POST.get('tipo', '')
        monto = request.POST.get('monto', '')
        try:
            monto = float(monto)
        except (ValueError, TypeError):
            messages.error(request, 'Monto inválido.')
            return redirect('app_padre:limites', pk=pk)

        if tipo not in ['diario', 'semanal', 'mensual']:
            messages.error(request, 'Tipo de límite inválido.')
            return redirect('app_padre:limites', pk=pk)
        if monto <= 0:
            messages.error(request, 'El monto debe ser mayor a cero.')
            return redirect('app_padre:limites', pk=pk)

        LimiteGasto.objects.update_or_create(
            padre=padre, estudiante=estudiante, tipo=tipo,
            defaults={'monto': monto, 'activo': True},
        )
        messages.success(request, f'Límite {tipo} de ${monto:,.0f} guardado.')
        return redirect('app_padre:limites', pk=pk)

    limites_qs = LimiteGasto.objects.filter(padre=padre, estudiante=estudiante)
    limites_data = []
    for l in limites_qs:
        limites_data.append({
            'limite': l,
            'gasto': l.gasto_actual(),
            'pct': l.porcentaje_uso,
            'disponible': l.disponible,
        })

    return render(request, 'app_padre/limites.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'limites_data': limites_data,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# RESTRICCIONES ALIMENTICIAS
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def restricciones(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'delete':
            rid = request.POST.get('restriccion_id')
            RestriccionAlimento.objects.filter(pk=rid, padre=padre).delete()
            messages.success(request, 'Restricción eliminada.')
            return redirect('app_padre:restricciones', pk=pk)

        if action == 'toggle':
            rid = request.POST.get('restriccion_id')
            r = get_object_or_404(RestriccionAlimento, pk=rid, padre=padre)
            r.activo = not r.activo
            r.save(update_fields=['activo'])
            return redirect('app_padre:restricciones', pk=pk)

        tipo_obj  = request.POST.get('tipo_obj', '')
        obj_id    = request.POST.get('obj_id', '')
        motivo    = request.POST.get('motivo', '').strip()
        aplica_a  = request.POST.get('aplica_a', 'hijo')  # 'hijo' o 'todos'

        prod_id = cat_id = None
        if tipo_obj == 'producto':
            prod_id = obj_id
        elif tipo_obj == 'categoria':
            cat_id = obj_id
        else:
            messages.error(request, 'Selecciona un producto o categoría.')
            return redirect('app_padre:restricciones', pk=pk)

        est_fk = estudiante if aplica_a == 'hijo' else None

        RestriccionAlimento.objects.create(
            padre=padre, estudiante=est_fk,
            producto_id=prod_id, categoria_id=cat_id,
            motivo=motivo, activo=True,
        )
        messages.success(request, 'Restricción añadida correctamente.')
        return redirect('app_padre:restricciones', pk=pk)

    restricciones_qs = RestriccionAlimento.objects.filter(
        Q(estudiante=estudiante) | Q(estudiante__isnull=True, padre=padre),
    ).select_related('producto', 'categoria', 'estudiante__perfil__user')

    productos   = Producto.objects.filter(disponible=True).select_related('categoria').order_by('nombre')
    categorias  = Categoria.objects.filter(activa=True)

    return render(request, 'app_padre/restricciones.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'restricciones': restricciones_qs,
        'productos': productos,
        'categorias': categorias,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# HORARIOS DE COMPRA
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def horarios(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'delete':
            hid = request.POST.get('horario_id')
            HorarioCompra.objects.filter(pk=hid, padre=padre).delete()
            messages.success(request, 'Horario eliminado.')
            return redirect('app_padre:horarios', pk=pk)

        if action == 'toggle':
            hid = request.POST.get('horario_id')
            h = get_object_or_404(HorarioCompra, pk=hid, padre=padre)
            h.activo = not h.activo
            h.save(update_fields=['activo'])
            return redirect('app_padre:horarios', pk=pk)

        nombre      = request.POST.get('nombre', '').strip() or 'Recreo'
        hora_inicio = request.POST.get('hora_inicio', '')
        hora_fin    = request.POST.get('hora_fin', '')

        if not hora_inicio or not hora_fin:
            messages.error(request, 'Hora de inicio y fin son obligatorias.')
            return redirect('app_padre:horarios', pk=pk)
        if hora_inicio >= hora_fin:
            messages.error(request, 'La hora de inicio debe ser anterior a la hora de fin.')
            return redirect('app_padre:horarios', pk=pk)

        HorarioCompra.objects.create(
            padre=padre, estudiante=estudiante,
            nombre=nombre, hora_inicio=hora_inicio, hora_fin=hora_fin,
        )
        messages.success(request, f'Horario "{nombre}" creado.')
        return redirect('app_padre:horarios', pk=pk)

    horarios_qs = HorarioCompra.objects.filter(padre=padre, estudiante=estudiante)

    return render(request, 'app_padre/horarios.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'horarios': horarios_qs,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# REALIZAR PEDIDO PARA HIJO
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def pedido_padre(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)

    # Restricciones activas del estudiante
    restricciones_prod_ids = set(
        RestriccionAlimento.objects.filter(
            Q(estudiante=estudiante) | Q(estudiante__isnull=True, padre=padre),
            activo=True, producto__isnull=False,
        ).values_list('producto_id', flat=True)
    )
    restricciones_cat_ids = set(
        RestriccionAlimento.objects.filter(
            Q(estudiante=estudiante) | Q(estudiante__isnull=True, padre=padre),
            activo=True, categoria__isnull=False,
        ).values_list('categoria_id', flat=True)
    )

    if request.method == 'POST':
        fuente    = request.POST.get('fuente', 'saldo_hijo')
        nota_ped  = request.POST.get('nota', '').strip()
        carrito   = {}
        for key, val in request.POST.items():
            if key.startswith('qty_'):
                try:
                    prod_id = int(key[4:])
                    qty     = int(val)
                    if qty > 0:
                        carrito[prod_id] = qty
                except (ValueError, TypeError):
                    pass

        if not carrito:
            messages.error(request, 'El carrito está vacío.')
            return redirect('app_padre:pedido_padre', pk=pk)

        # Validar productos y calcular total
        total = Decimal('0')
        lineas = []
        for prod_id, qty in carrito.items():
            try:
                prod = Producto.objects.get(pk=prod_id, disponible=True)
            except Producto.DoesNotExist:
                messages.error(request, 'Uno de los productos no está disponible.')
                return redirect('app_padre:pedido_padre', pk=pk)
            if prod.id in restricciones_prod_ids or prod.categoria_id in restricciones_cat_ids:
                messages.error(request, f'"{prod.nombre}" está restringido para este estudiante.')
                return redirect('app_padre:pedido_padre', pk=pk)
            subtotal = Decimal(str(prod.precio_venta)) * qty
            total   += subtotal
            lineas.append((prod, qty, subtotal))

        # Validar fuente
        if fuente not in ('saldo_hijo', 'saldo_padre'):
            fuente = 'saldo_hijo'

        # Crear pedido en transacción atómica con lock
        try:
            with transaction.atomic():
                if fuente == 'saldo_hijo':
                    est_locked = Estudiante.objects.select_for_update().get(pk=estudiante.pk)
                    if est_locked.saldo < total:
                        messages.error(request, f'El estudiante no tiene saldo suficiente (disponible: ${est_locked.saldo:,.0f}).')
                        return redirect('app_padre:pedido_padre', pk=pk)
                else:
                    padre_locked = Padre.objects.select_for_update().get(pk=padre.pk)
                    est_locked   = estudiante
                    if padre_locked.saldo < total:
                        messages.error(request, f'Tu saldo no es suficiente (disponible: ${padre_locked.saldo:,.0f}).')
                        return redirect('app_padre:pedido_padre', pk=pk)

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

                PedidoPadre.objects.create(pedido=pedido, padre=padre, fuente=fuente, nota=nota_ped)

                # Descontar saldo
                if fuente == 'saldo_hijo':
                    est_locked.saldo -= total
                    est_locked.save(update_fields=['saldo'])
                else:
                    padre_locked.saldo -= total
                    padre_locked.save(update_fields=['saldo'])
        except Exception:
            messages.error(request, 'Error al procesar el pedido. Intenta de nuevo.')
            return redirect('app_padre:pedido_padre', pk=pk)

        Notificacion.objects.create(
            padre=padre,
            tipo='pedido_padre',
            titulo='Pedido realizado',
            mensaje=f'Realizaste un pedido de ${total:,.0f} para {estudiante.perfil.user.get_full_name()}. Ticket: {pedido.ticket}',
            url_accion='/padre/historial/',
        )

        messages.success(request, f'Pedido {pedido.ticket} creado exitosamente por ${total:,.0f}.')
        return redirect('app_padre:historial')

    productos    = Producto.objects.filter(disponible=True).select_related('categoria').order_by('categoria', 'nombre')
    categorias   = Categoria.objects.filter(activa=True)

    prods_lista = []
    for p in productos:
        restringido = p.id in restricciones_prod_ids or p.categoria_id in restricciones_cat_ids
        prods_lista.append((p, restringido))

    return render(request, 'app_padre/pedido_padre.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'prods_lista': prods_lista,
        'categorias': categorias,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS PROGRAMADOS
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def pedidos_programados(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'cancel':
            pid = request.POST.get('programado_id')
            prog = get_object_or_404(PedidoProgramado, pk=pid, padre=padre, estado='activo')
            prog.estado = 'cancelado'
            prog.save(update_fields=['estado'])
            messages.success(request, 'Pedido programado cancelado.')
            return redirect('app_padre:pedidos_programados', pk=pk)

        fecha     = request.POST.get('fecha_entrega', '')
        hora      = request.POST.get('hora_entrega', '') or None
        fuente    = request.POST.get('fuente', 'saldo_hijo')
        nota      = request.POST.get('nota', '').strip()

        if not fecha:
            messages.error(request, 'La fecha de entrega es obligatoria.')
            return redirect('app_padre:pedidos_programados', pk=pk)

        carrito = {}
        for key, val in request.POST.items():
            if key.startswith('qty_'):
                try:
                    prod_id = int(key[4:])
                    qty     = int(val)
                    if qty > 0:
                        carrito[prod_id] = qty
                except (ValueError, TypeError):
                    pass

        if not carrito:
            messages.error(request, 'Agrega al menos un producto.')
            return redirect('app_padre:pedidos_programados', pk=pk)

        prog = PedidoProgramado.objects.create(
            padre=padre, estudiante=estudiante,
            fecha_entrega=fecha, hora_entrega=hora,
            fuente=fuente, nota=nota,
        )
        for prod_id, qty in carrito.items():
            try:
                prod = Producto.objects.get(pk=prod_id)
                DetalleProgramado.objects.create(pedido_prog=prog, producto=prod, cantidad=qty)
            except Producto.DoesNotExist:
                pass

        messages.success(request, f'Pedido programado para el {fecha}.')
        return redirect('app_padre:pedidos_programados', pk=pk)

    programados = PedidoProgramado.objects.filter(
        padre=padre, estudiante=estudiante
    ).prefetch_related('detalles__producto').order_by('fecha_entrega')

    productos = Producto.objects.filter(disponible=True).select_related('categoria').order_by('nombre')

    return render(request, 'app_padre/pedidos_programados.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'programados': programados,
        'productos': productos,
        'hoy': timezone.now().date().isoformat(),
    }))


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICACIONES
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def notificaciones(request):
    padre = _get_padre(request)

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'marcar_todas':
            Notificacion.objects.filter(padre=padre, leida=False).update(leida=True)
            messages.success(request, 'Todas las notificaciones marcadas como leídas.')
        elif action == 'marcar_una':
            nid = request.POST.get('notif_id')
            Notificacion.objects.filter(pk=nid, padre=padre).update(leida=True)
        elif action == 'eliminar':
            nid = request.POST.get('notif_id')
            Notificacion.objects.filter(pk=nid, padre=padre).delete()
        elif action == 'eliminar_leidas':
            Notificacion.objects.filter(padre=padre, leida=True).delete()
        return redirect('app_padre:notificaciones')

    notifs_qs = Notificacion.objects.filter(padre=padre).order_by('-fecha')
    n_no_leidas = notifs_qs.filter(leida=False).count()

    return render(request, 'app_padre/notificaciones.html', _ctx_padre(padre, {
        'padre': padre,
        'notificaciones': notifs_qs,
        'n_no_leidas': n_no_leidas,
        'n_notif': n_no_leidas,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# SALDO DEL PADRE
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def saldo_padre(request):
    padre = _get_padre(request)

    if request.method == 'POST':
        try:
            monto = float(request.POST.get('monto', 0))
            nota  = request.POST.get('nota', '').strip()
        except (ValueError, TypeError):
            messages.error(request, 'Monto inválido.')
            return redirect('app_padre:saldo_padre')

        comprobante = request.FILES.get('comprobante')

        if monto <= 0:
            messages.error(request, 'El monto debe ser mayor a cero.')
        elif monto > 2_000_000:
            messages.error(request, 'El monto máximo por recarga es $2.000.000.')
        else:
            # Recarga de saldo del PADRE (vinculada al primer hijo para compatibilidad)
            # Se crea como RecargaSaldo pendiente pero apuntando a un estudiante dummy
            # En su lugar generamos una notificación interna
            Notificacion.objects.create(
                padre=padre,
                tipo='recarga_pendiente',
                titulo='Recarga de saldo propio en revisión',
                mensaje=f'Tu solicitud de recarga de ${monto:,.0f} para tu saldo personal está siendo revisada.',
                url_accion='/padre/saldo/',
            )
            messages.success(request, f'Solicitud de recarga de ${monto:,.0f} enviada. Tu saldo se actualizará cuando sea aprobada.')
            return redirect('app_padre:saldo_padre')

    # Historial de pedidos realizados por el padre con su propio saldo
    pedidos_propios = PedidoPadre.objects.filter(
        padre=padre, fuente='saldo_padre'
    ).select_related('pedido__estudiante__perfil__user').order_by('-created_at')[:20]

    gasto_saldo_propio = sum(float(pp.pedido.total) for pp in pedidos_propios)

    return render(request, 'app_padre/saldo_padre.html', _ctx_padre(padre, {
        'padre': padre,
        'pedidos_propios': pedidos_propios,
        'gasto_saldo_propio': gasto_saldo_propio,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def perfil(request):
    padre = _get_padre(request)
    user  = request.user

    if request.method == 'POST':
        action = request.POST.get('action', 'datos')

        if action == 'datos':
            user.first_name      = request.POST.get('first_name', '').strip()
            user.last_name       = request.POST.get('last_name',  '').strip()
            user.email           = request.POST.get('email',      '').strip()
            user.perfil.telefono = request.POST.get('telefono',   '').strip()
            padre.documento      = request.POST.get('documento',  '').strip()
            user.save()
            user.perfil.save()
            padre.save()
            messages.success(request, 'Datos actualizados correctamente.')

        elif action == 'password':
            old_pw  = request.POST.get('old_password',  '')
            new_pw1 = request.POST.get('new_password1', '')
            new_pw2 = request.POST.get('new_password2', '')
            if not user.check_password(old_pw):
                messages.error(request, 'La contraseña actual es incorrecta.')
            elif new_pw1 != new_pw2:
                messages.error(request, 'Las contraseñas nuevas no coinciden.')
            elif len(new_pw1) < 8:
                messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            else:
                user.set_password(new_pw1)
                user.save()
                messages.success(request, 'Contraseña actualizada. Inicia sesión de nuevo.')
                return redirect('authentication:login')

        return redirect('app_padre:perfil')

    n_hijos        = padre.hijos.count()
    n_recargas     = RecargaSaldo.objects.filter(padre=padre).count()
    total_recargado = RecargaSaldo.objects.filter(padre=padre, estado='aprobada').aggregate(t=Sum('monto'))['t'] or 0
    n_pedidos_padre = PedidoPadre.objects.filter(padre=padre).count()

    return render(request, 'app_padre/perfil.html', _ctx_padre(padre, {
        'padre': padre,
        'n_hijos': n_hijos,
        'n_recargas': n_recargas,
        'total_recargado': total_recargado,
        'n_pedidos_padre': n_pedidos_padre,
    }))


# ══════════════════════════════════════════════════════════════════════════════
# API: NOTIFICACIONES (polling AJAX)
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def api_notificaciones(request):
    padre = _get_padre(request)
    n = Notificacion.objects.filter(padre=padre, leida=False).count()
    ultimas = list(
        Notificacion.objects.filter(padre=padre, leida=False)
        .order_by('-fecha')[:5]
        .values('id', 'tipo', 'titulo', 'mensaje', 'fecha', 'url_accion')
    )
    for item in ultimas:
        item['fecha'] = item['fecha'].strftime('%d/%m %H:%M')
    return JsonResponse({'n': n, 'items': ultimas})


# ══════════════════════════════════════════════════════════════════════════════
# ALERGIAS
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def alergias(request, pk):
    padre      = _get_padre(request)
    estudiante = get_object_or_404(Estudiante, pk=pk, padre=padre)
    alergias_qs = AlergiaEstudiante.objects.filter(padre=padre, estudiante=estudiante).order_by('-gravedad', 'nombre')

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        if accion == 'crear':
            nombre   = request.POST.get('nombre', '').strip()
            tipo     = request.POST.get('tipo', 'alergia')
            gravedad = request.POST.get('gravedad', 'leve')
            notas    = request.POST.get('notas', '').strip()

            if not nombre:
                messages.error(request, 'El nombre de la alergia es obligatorio.')
                return redirect('app_padre:alergias', pk=pk)

            if tipo not in dict(AlergiaEstudiante.TIPO_CHOICES):
                tipo = 'alergia'
            if gravedad not in dict(AlergiaEstudiante.GRAVEDAD_CHOICES):
                gravedad = 'leve'

            AlergiaEstudiante.objects.create(
                padre=padre, estudiante=estudiante,
                nombre=nombre, tipo=tipo, gravedad=gravedad, notas=notas,
            )
            messages.success(request, f'Alergia "{nombre}" registrada.')

        elif accion == 'eliminar':
            alergia_pk = request.POST.get('alergia_pk', '')
            alergia = get_object_or_404(AlergiaEstudiante, pk=alergia_pk, padre=padre, estudiante=estudiante)
            alergia.delete()
            messages.success(request, 'Alergia eliminada.')

        elif accion == 'toggle':
            alergia_pk = request.POST.get('alergia_pk', '')
            alergia = get_object_or_404(AlergiaEstudiante, pk=alergia_pk, padre=padre, estudiante=estudiante)
            alergia.activo = not alergia.activo
            alergia.save(update_fields=['activo'])

        return redirect('app_padre:alergias', pk=pk)

    return render(request, 'app_padre/alergias.html', _ctx_padre(padre, {
        'padre': padre,
        'estudiante': estudiante,
        'alergias': alergias_qs,
        'TIPO_CHOICES': AlergiaEstudiante.TIPO_CHOICES,
        'GRAVEDAD_CHOICES': AlergiaEstudiante.GRAVEDAD_CHOICES,
    }))
