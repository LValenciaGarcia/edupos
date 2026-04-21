from django.shortcuts import render, redirect
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction, models as dm
from django.utils import timezone
import json

from authentication.models import Perfil, Estudiante, Docente, Sede
from app_admin.models import Producto, Categoria
from .models import VentaEmpleado, DetalleVenta, TurnoCaja, AnulacionVenta


# ══════════════════════════════════════════════════════════════════════════════
# DECORADOR
# ══════════════════════════════════════════════════════════════════════════════

def empleado_required(view_func):
    @login_required(login_url='/login/')
    def wrapper(request, *args, **kwargs):
        try:
            perfil = request.user.perfil
            if not perfil.activo:
                messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
                return redirect('authentication:login')
            if perfil.rol != 'empleado':
                messages.error(request, 'Acceso restringido.')
                return redirect('core:home')
        except Perfil.DoesNotExist:
            return redirect('authentication:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _empleado(request):
    return request.user.perfil.empleado


def _sede_activa(request):
    emp = _empleado(request)
    if emp.es_global:
        return None
    return emp.sedes.filter(activa=True).first()


def _ventas_qs(request):
    emp  = _empleado(request)
    sede = _sede_activa(request)
    qs   = VentaEmpleado.objects.filter(empleado=emp)
    if not emp.es_global and sede:
        qs = qs.filter(sede=sede)
    return qs


def _turno_activo(request):
    emp = _empleado(request)
    return TurnoCaja.objects.filter(empleado=emp, estado='abierto').first()


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def dashboard(request):
    emp   = _empleado(request)
    sede  = _sede_activa(request)
    hoy   = timezone.now().date()
    turno = _turno_activo(request)

    ventas_hoy    = _ventas_qs(request).filter(fecha__date=hoy, anulada=False)
    total_hoy     = sum(float(v.total) for v in ventas_hoy)
    num_ventas    = ventas_hoy.count()
    total_efectivo = sum(float(v.total) for v in ventas_hoy if v.tipo_pago == 'efectivo')

    return render(request, 'app_empleado/dashboard.html', {
        'empleado':         emp,
        'sede':             sede,
        'total_hoy':        total_hoy,
        'num_ventas':       num_ventas,
        'total_efectivo':   total_efectivo,
        'turno':            turno,
        'ventas_recientes': ventas_hoy.order_by('-fecha').select_related(
            'estudiante__perfil__user', 'docente__perfil__user'
        )[:6],
    })


# ══════════════════════════════════════════════════════════════════════════════
# TURNO DE CAJA
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def turno(request):
    emp          = _empleado(request)
    sede         = _sede_activa(request)
    turno_activo = _turno_activo(request)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'abrir':
            if turno_activo:
                messages.warning(request, 'Ya tienes un turno abierto.')
            else:
                sede_usar = sede
                if not sede_usar and emp.es_global:
                    sede_usar = Sede.objects.filter(activa=True).first()
                if not sede_usar:
                    messages.error(request, 'No tienes sede asignada activa.')
                else:
                    TurnoCaja.objects.create(
                        empleado=emp,
                        sede=sede_usar,
                        efectivo_inicial=request.POST.get('efectivo_inicial') or 0,
                        nota=request.POST.get('nota', ''),
                    )
                    messages.success(request, 'Turno abierto. ¡Buen turno!')
                    return redirect('app_empleado:turno')

        elif accion == 'cerrar' and turno_activo:
            turno_activo.efectivo_final = request.POST.get('efectivo_final') or 0
            turno_activo.estado  = 'cerrado'
            turno_activo.cierre  = timezone.now()
            turno_activo.nota    = request.POST.get('nota_cierre', '')
            turno_activo.save()
            total = float(turno_activo.total_ventas)
            messages.success(request, f'Turno cerrado. Total vendido: ${total:,.0f}')
            return redirect('app_empleado:turno')

    historial = TurnoCaja.objects.filter(empleado=emp).order_by('-apertura')[:10]

    return render(request, 'app_empleado/turno.html', {
        'empleado':     emp,
        'sede':         sede,
        'turno_activo': turno_activo,
        'historial':    historial,
    })


# ══════════════════════════════════════════════════════════════════════════════
# CAJA (POS)
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def caja(request):
    emp  = _empleado(request)
    sede = _sede_activa(request)

    productos  = (
        Producto.objects
        .filter(disponible=True)
        .select_related('categoria')
        .order_by('categoria__nombre', 'nombre')
    )
    categorias = Categoria.objects.filter(activa=True)
    turno      = _turno_activo(request)

    return render(request, 'app_empleado/caja.html', {
        'empleado':   emp,
        'sede':       sede,
        'productos':  productos,
        'categorias': categorias,
        'turno':      turno,
    })


@empleado_required
def procesar_venta(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        data         = json.loads(request.body)
        items        = data.get('items', [])
        tipo_pago    = data.get('tipo_pago', 'efectivo')
        nota         = data.get('nota', '')
        cliente_id   = data.get('cliente_id')
        tipo_cliente = data.get('tipo_cliente', '')

        if not items:
            return JsonResponse({'ok': False, 'error': 'El carrito está vacío'})

        emp  = _empleado(request)
        sede = _sede_activa(request)

        if not sede and not emp.es_global:
            return JsonResponse({'ok': False, 'error': 'No tienes ninguna sede asignada.'})
        if emp.es_global and not sede:
            sede = Sede.objects.filter(activa=True).first()
        if not sede:
            return JsonResponse({'ok': False, 'error': 'No hay sedes activas en el sistema.'})

        turno_activo = _turno_activo(request)

        with transaction.atomic():
            validados = []
            for item in items:
                p        = Producto.objects.select_for_update().get(pk=item['id'])
                cantidad = int(item['cantidad'])
                if not p.disponible:
                    return JsonResponse({'ok': False, 'error': f'"{p.nombre}" ya no está disponible.'})
                if p.tipo == 'simple' and p.stock < cantidad:
                    return JsonResponse({'ok': False, 'error': f'Stock insuficiente para "{p.nombre}" (disponible: {p.stock}).'})
                validados.append((p, cantidad))

            total_calculado = sum(float(p.precio_venta) * c for p, c in validados)

            venta = VentaEmpleado(
                empleado=emp,
                sede=sede,
                turno=turno_activo,
                tipo_pago=tipo_pago,
                nota=nota,
            )

            fiado_usado = 0

            if tipo_pago == 'cuenta_estudiante' and cliente_id:
                est = Estudiante.objects.select_for_update().get(pk=cliente_id)
                if float(est.saldo) < total_calculado:
                    return JsonResponse({'ok': False, 'error': f'Saldo insuficiente. Disponible: ${est.saldo:,.0f}'})
                venta.estudiante = est

            elif tipo_pago == 'cuenta_docente' and cliente_id:
                doc = Docente.objects.select_for_update().get(pk=cliente_id)
                if doc.saldo_total_disponible < total_calculado:
                    return JsonResponse({'ok': False, 'error': f'Saldo/crédito insuficiente. Disponible: ${doc.saldo_total_disponible:,.0f}'})
                # Calculate fiado used
                if total_calculado > float(doc.saldo):
                    fiado_usado = total_calculado - float(doc.saldo)
                venta.docente     = doc
                venta.fiado_usado = fiado_usado

            venta.save()

            for producto, cantidad in validados:
                DetalleVenta.objects.create(
                    venta=venta,
                    producto=producto,
                    cantidad=cantidad,
                    precio_unit=producto.precio_venta,
                )
                if producto.tipo == 'simple':
                    producto.stock -= cantidad
                    producto.save(update_fields=['stock'])

            venta.recalcular_total()

            # Descontar saldo del cliente
            if tipo_pago == 'cuenta_estudiante' and venta.estudiante:
                venta.estudiante.saldo = float(venta.estudiante.saldo) - float(venta.total)
                venta.estudiante.save(update_fields=['saldo'])

            elif tipo_pago == 'cuenta_docente' and venta.docente:
                doc = venta.docente
                if float(venta.total) <= float(doc.saldo):
                    doc.saldo = float(doc.saldo) - float(venta.total)
                else:
                    exceso          = float(venta.total) - float(doc.saldo)
                    doc.saldo       = 0
                    doc.deuda_fiado = float(doc.deuda_fiado) + exceso
                doc.save(update_fields=['saldo', 'deuda_fiado'])

        detalles = [
            {'nombre': d.producto.nombre, 'cantidad': d.cantidad, 'subtotal': float(d.subtotal)}
            for d in venta.detalles.select_related('producto').all()
        ]
        return JsonResponse({'ok': True, 'ticket': venta.ticket, 'total': float(venta.total), 'detalles': detalles})

    except Producto.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Un producto del carrito ya no existe.'})
    except Estudiante.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Estudiante no encontrado.'})
    except Docente.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Docente no encontrado.'})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@empleado_required
def buscar_cliente(request):
    q    = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', 'estudiante')

    results = []
    if len(q) >= 2:
        if tipo == 'estudiante':
            qs = Estudiante.objects.filter(perfil__activo=True).filter(
                dm.Q(codigo__icontains=q) |
                dm.Q(perfil__user__first_name__icontains=q) |
                dm.Q(perfil__user__last_name__icontains=q)
            ).select_related('perfil__user')[:10]
            results = [
                {'id': e.pk, 'nombre': e.perfil.user.get_full_name(), 'codigo': e.codigo, 'saldo': float(e.saldo)}
                for e in qs
            ]
        elif tipo == 'docente':
            qs = Docente.objects.filter(perfil__activo=True).filter(
                dm.Q(perfil__user__first_name__icontains=q) |
                dm.Q(perfil__user__last_name__icontains=q) |
                dm.Q(documento__icontains=q)
            ).select_related('perfil__user')[:10]
            results = [
                {'id': d.pk, 'nombre': d.perfil.user.get_full_name(), 'saldo': float(d.saldo), 'credito': float(d.credito_disponible)}
                for d in qs
            ]

    return JsonResponse({'results': results})


# ══════════════════════════════════════════════════════════════════════════════
# VENTAS (historial)
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def ventas(request):
    emp  = _empleado(request)
    sede = _sede_activa(request)

    qs = _ventas_qs(request).select_related(
        'sede', 'estudiante__perfil__user', 'docente__perfil__user'
    )

    fecha = request.GET.get('fecha', '')
    if fecha:
        qs = qs.filter(fecha__date=fecha)
    else:
        fecha = str(timezone.now().date())
        qs    = qs.filter(fecha__date=fecha)

    ventas_list    = list(qs.order_by('-fecha'))
    total_dia      = sum(float(v.total) for v in ventas_list if not v.anulada)
    total_efectivo = sum(float(v.total) for v in ventas_list if not v.anulada and v.tipo_pago == 'efectivo')
    num_anuladas   = sum(1 for v in ventas_list if v.anulada)

    return render(request, 'app_empleado/ventas.html', {
        'ventas':         ventas_list,
        'empleado':       emp,
        'sede':           sede,
        'total_dia':      total_dia,
        'total_efectivo': total_efectivo,
        'num_anuladas':   num_anuladas,
        'fecha':          fecha,
    })


@empleado_required
def anular_venta(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        data      = json.loads(request.body)
        ticket    = data.get('ticket', '').strip()
        motivo    = data.get('motivo', '').strip()
        sup_user  = data.get('supervisor_usuario', '').strip()
        sup_pass  = data.get('supervisor_password', '').strip()

        if not all([ticket, motivo, sup_user, sup_pass]):
            return JsonResponse({'ok': False, 'error': 'Completa todos los campos.'})

        # Verificar credenciales del supervisor
        supervisor = authenticate(request, username=sup_user, password=sup_pass)
        if not supervisor:
            return JsonResponse({'ok': False, 'error': 'Credenciales de supervisor incorrectas.'})

        try:
            sup_perfil = supervisor.perfil
            if sup_perfil.rol == 'admin':
                pass  # Admin siempre puede autorizar
            elif sup_perfil.rol == 'empleado' and sup_perfil.empleado.cargo == 'supervisor':
                pass  # Supervisor de sede puede autorizar
            else:
                return JsonResponse({'ok': False, 'error': 'El usuario no tiene permisos de supervisor.'})
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Usuario sin perfil válido.'})

        emp = _empleado(request)
        try:
            venta = VentaEmpleado.objects.get(ticket=ticket, empleado=emp)
        except VentaEmpleado.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Ticket no encontrado en tus ventas.'})

        if venta.anulada:
            return JsonResponse({'ok': False, 'error': 'Esta venta ya fue anulada.'})

        with transaction.atomic():
            # Revertir saldo
            if venta.tipo_pago == 'cuenta_estudiante' and venta.estudiante:
                venta.estudiante.saldo = float(venta.estudiante.saldo) + float(venta.total)
                venta.estudiante.save(update_fields=['saldo'])

            elif venta.tipo_pago == 'cuenta_docente' and venta.docente:
                doc = venta.docente
                # Usar fiado_usado guardado en la venta para revertir exactamente
                fiado_rev  = float(venta.fiado_usado)
                saldo_rev  = float(venta.total) - fiado_rev
                doc.deuda_fiado = max(0, float(doc.deuda_fiado) - fiado_rev)
                doc.saldo       = float(doc.saldo) + saldo_rev
                doc.save(update_fields=['saldo', 'deuda_fiado'])

            # Restaurar stock
            for detalle in venta.detalles.select_related('producto').all():
                if detalle.producto.tipo == 'simple':
                    detalle.producto.stock += detalle.cantidad
                    detalle.producto.save(update_fields=['stock'])

            venta.anulada = True
            venta.save(update_fields=['anulada'])

            AnulacionVenta.objects.create(
                venta=venta,
                supervisor_user=supervisor,
                motivo=motivo,
            )

        return JsonResponse({'ok': True, 'mensaje': f'Venta {ticket} anulada. Saldo/stock restaurados.'})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


# ══════════════════════════════════════════════════════════════════════════════
# INVENTARIO (solo lectura)
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def inventario_empleado(request):
    emp  = _empleado(request)
    sede = _sede_activa(request)

    productos  = Producto.objects.select_related('categoria').order_by('categoria__nombre', 'nombre')
    categorias = Categoria.objects.filter(activa=True)

    q      = request.GET.get('q', '').strip()
    cat_id = request.GET.get('cat', '')

    if q:
        productos = productos.filter(nombre__icontains=q)
    if cat_id:
        productos = productos.filter(categoria__nombre=cat_id)

    total_productos = productos.filter(disponible=True).count()
    sin_stock_count = sum(1 for p in productos if p.sin_stock)
    stock_bajo_count = sum(1 for p in productos if p.stock_bajo and not p.sin_stock)

    return render(request, 'app_empleado/inventario.html', {
        'empleado':        emp,
        'sede':            sede,
        'productos':       productos,
        'categorias':      categorias,
        'q':               q,
        'cat_id':          cat_id,
        'total_productos': total_productos,
        'sin_stock_count': sin_stock_count,
        'stock_bajo_count': stock_bajo_count,
    })


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL DE CLIENTES (solo lectura)
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def historial_cliente(request):
    emp  = _empleado(request)
    sede = _sede_activa(request)

    q            = request.GET.get('q', '').strip()
    tipo         = request.GET.get('tipo', 'estudiante')
    cliente_obj  = None
    ventas_list  = []
    total_cliente = 0

    if q and len(q) >= 2:
        if tipo == 'estudiante':
            cliente_obj = Estudiante.objects.filter(
                dm.Q(codigo__icontains=q) |
                dm.Q(perfil__user__first_name__icontains=q) |
                dm.Q(perfil__user__last_name__icontains=q)
            ).select_related('perfil__user').first()
            if cliente_obj:
                ventas_list  = list(
                    VentaEmpleado.objects
                    .filter(estudiante=cliente_obj, anulada=False)
                    .prefetch_related('detalles__producto')
                    .order_by('-fecha')[:30]
                )
                total_cliente = sum(float(v.total) for v in ventas_list)

        elif tipo == 'docente':
            cliente_obj = Docente.objects.filter(
                dm.Q(perfil__user__first_name__icontains=q) |
                dm.Q(perfil__user__last_name__icontains=q) |
                dm.Q(documento__icontains=q)
            ).select_related('perfil__user').first()
            if cliente_obj:
                ventas_list  = list(
                    VentaEmpleado.objects
                    .filter(docente=cliente_obj, anulada=False)
                    .prefetch_related('detalles__producto')
                    .order_by('-fecha')[:30]
                )
                total_cliente = sum(float(v.total) for v in ventas_list)

    return render(request, 'app_empleado/clientes.html', {
        'empleado':    emp,
        'sede':        sede,
        'q':           q,
        'tipo':        tipo,
        'cliente_obj': cliente_obj,
        'ventas_list': ventas_list,
        'total_cliente': total_cliente,
    })


# ══════════════════════════════════════════════════════════════════════════════
# PERFIL
# ══════════════════════════════════════════════════════════════════════════════

@empleado_required
def perfil(request):
    emp  = _empleado(request)
    user = request.user

    if request.method == 'POST':
        telefono = request.POST.get('telefono', '').strip()
        email    = request.POST.get('email', '').strip()

        user.perfil.telefono = telefono
        user.perfil.save(update_fields=['telefono'])

        if email and email != user.email:
            user.email = email
            user.save(update_fields=['email'])

        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('app_empleado:perfil')

    return render(request, 'app_empleado/perfil.html', {
        'empleado': emp,
        'sede':     _sede_activa(request),
    })
