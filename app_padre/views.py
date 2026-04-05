from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone

from authentication.models import Perfil, Padre, Estudiante
from app_admin.models import Producto, Categoria, Pedido
from .models import RecargaSaldo


# ══════════════════════════════════════════════════════════════════════════════
# DECORADOR
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


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def dashboard(request):
    padre = _get_padre(request)
    hijos = padre.hijos.select_related('perfil__user').order_by('perfil__user__first_name')

    saldo_total = hijos.aggregate(total=Sum('saldo'))['total'] or 0

    ahora = timezone.now()
    gasto_mes = Pedido.objects.filter(
        estudiante__padre=padre,
        estado='entregado',
        fecha_pedido__month=ahora.month,
        fecha_pedido__year=ahora.year,
    ).aggregate(total=Sum('total'))['total'] or 0

    pedidos_recientes = Pedido.objects.filter(
        estudiante__padre=padre
    ).select_related('estudiante__perfil__user').order_by('-fecha_pedido')[:6]

    recargas_recientes = RecargaSaldo.objects.filter(
        padre=padre
    ).select_related('estudiante__perfil__user').order_by('-fecha')[:5]

    return render(request, 'app_padre/dashboard.html', {
        'padre': padre,
        'hijos': hijos,
        'n_hijos': hijos.count(),
        'saldo_total': saldo_total,
        'gasto_mes': gasto_mes,
        'pedidos_recientes': pedidos_recientes,
        'recargas_recientes': recargas_recientes,
    })


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
        hijos_data.append({
            'hijo': hijo,
            'recargas': ultimas_recargas,
            'pedidos': ultimos_pedidos,
        })

    return render(request, 'app_padre/hijos.html', {
        'padre': padre,
        'hijos_data': hijos_data,
    })


# ══════════════════════════════════════════════════════════════════════════════
# CREAR ESTUDIANTE
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def crear_estudiante(request):
    padre = _get_padre(request)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name',  '').strip()
        username   = request.POST.get('username',   '').strip()
        password1  = request.POST.get('password1',  '')
        password2  = request.POST.get('password2',  '')
        grado      = request.POST.get('grado',      '').strip()
        codigo     = request.POST.get('codigo',     '').strip()

        errores = []
        if not all([first_name, last_name, username, password1, grado, codigo]):
            errores.append('Todos los campos son obligatorios.')
        if password1 != password2:
            errores.append('Las contraseñas no coinciden.')
        if len(password1) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if User.objects.filter(username=username).exists():
            errores.append('Ese nombre de usuario ya está en uso.')
        if Estudiante.objects.filter(codigo=codigo).exists():
            errores.append('Ya existe un estudiante con ese código.')

        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, 'app_padre/crear_estudiante.html', {
                'padre': padre,
                'form_data': request.POST,
            })

        user = User.objects.create_user(
            username=username,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )
        perfil = Perfil.objects.create(user=user, rol='estudiante')
        Estudiante.objects.create(
            perfil=perfil, padre=padre,
            grado=grado, codigo=codigo, saldo=0
        )
        messages.success(request, f'Cuenta de {first_name} {last_name} creada exitosamente.')
        return redirect('app_padre:hijos')

    return render(request, 'app_padre/crear_estudiante.html', {'padre': padre})


# ══════════════════════════════════════════════════════════════════════════════
# RECARGAR SALDO
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

        if monto <= 0:
            messages.error(request, 'El monto debe ser mayor a cero.')
        elif monto > 1_000_000:
            messages.error(request, 'El monto máximo por recarga es $1.000.000.')
        else:
            from decimal import Decimal
            estudiante.saldo += Decimal(str(monto))
            estudiante.save(update_fields=['saldo'])
            RecargaSaldo.objects.create(
                estudiante=estudiante, padre=padre,
                monto=monto, nota=nota
            )
            nombre = estudiante.perfil.user.first_name or estudiante.perfil.user.username
            messages.success(request, f'Se recargaron ${monto:,.0f} a {nombre}.')
            return redirect('app_padre:hijos')

    historial = RecargaSaldo.objects.filter(estudiante=estudiante).order_by('-fecha')[:10]
    return render(request, 'app_padre/recargar_saldo.html', {
        'padre': padre,
        'estudiante': estudiante,
        'historial': historial,
    })


# ══════════════════════════════════════════════════════════════════════════════
# MENÚ (vitrina de productos)
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def menu(request):
    padre    = _get_padre(request)
    cat_slug = request.GET.get('cat', '')
    q        = request.GET.get('q', '').strip()

    productos = Producto.objects.filter(disponible=True).select_related('categoria').order_by('categoria', 'nombre')

    if cat_slug:
        productos = productos.filter(categoria__nombre=cat_slug)
    if q:
        productos = productos.filter(nombre__icontains=q)

    categorias = Categoria.objects.filter(activa=True)

    return render(request, 'app_padre/menu.html', {
        'padre': padre,
        'productos': productos,
        'categorias': categorias,
        'cat_activa': cat_slug,
        'q': q,
    })


# ══════════════════════════════════════════════════════════════════════════════
# HISTORIAL DE PEDIDOS
# ══════════════════════════════════════════════════════════════════════════════

@padre_required
def historial(request):
    padre    = _get_padre(request)
    hijo_pk  = request.GET.get('hijo',   '')
    estado   = request.GET.get('estado', '')

    hijos_qs = padre.hijos.select_related('perfil__user')

    pedidos = Pedido.objects.filter(
        estudiante__padre=padre
    ).select_related('estudiante__perfil__user').prefetch_related('detalles__producto').order_by('-fecha_pedido')

    if hijo_pk:
        pedidos = pedidos.filter(estudiante__pk=hijo_pk)
    if estado:
        pedidos = pedidos.filter(estado=estado)

    gasto_total = Pedido.objects.filter(
        estudiante__padre=padre, estado='entregado'
    ).aggregate(total=Sum('total'))['total'] or 0

    return render(request, 'app_padre/historial.html', {
        'padre': padre,
        'pedidos': pedidos[:60],
        'hijos': hijos_qs,
        'hijo_activo': hijo_pk,
        'estado_activo': estado,
        'gasto_total': gasto_total,
        'ESTADO_CHOICES': Pedido.ESTADO_CHOICES,
    })


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
            user.first_name        = request.POST.get('first_name', '').strip()
            user.last_name         = request.POST.get('last_name',  '').strip()
            user.email             = request.POST.get('email',      '').strip()
            user.perfil.telefono   = request.POST.get('telefono',   '').strip()
            padre.documento        = request.POST.get('documento',  '').strip()
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

    n_hijos   = padre.hijos.count()
    n_recargas = RecargaSaldo.objects.filter(padre=padre).count()
    total_recargado = RecargaSaldo.objects.filter(padre=padre).aggregate(
        t=Sum('monto')
    )['t'] or 0

    return render(request, 'app_padre/perfil.html', {
        'padre': padre,
        'n_hijos': n_hijos,
        'n_recargas': n_recargas,
        'total_recargado': total_recargado,
    })
