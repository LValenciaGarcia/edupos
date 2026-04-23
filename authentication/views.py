from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Perfil, Padre, Docente
from .utils import generar_username


# ─── LOGIN ────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        # Si tiene perfil → su dashboard
        if hasattr(request.user, 'perfil'):
            return _redirigir_por_rol(request.user)
        # Sin perfil (vino de Google y aún no eligió rol) → seleccionar_rol
        return redirect('authentication:seleccionar_rol')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user is not None:
            try:
                if not user.perfil.activo:
                    messages.error(request, 'Tu cuenta está desactivada. Contacta al administrador.')
                    return render(request, 'authentication/login.html')
            except Perfil.DoesNotExist:
                pass

            login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return _redirigir_por_rol(user)
        else:
            messages.error(request, 'Correo o contraseña incorrectos.')

    return render(request, 'authentication/login.html')


def _redirigir_por_rol(user):
    """Redirige al dashboard correspondiente según el rol del usuario."""
    try:
        rol = user.perfil.rol
        if rol == 'admin':
            return redirect('app_admin:dashboard')
        elif rol == 'padre':
            return redirect('app_padre:dashboard')
        elif rol == 'estudiante':
            return redirect('app_estudiante:dashboard')
        elif rol == 'docente':
            return redirect('app_docente:dashboard')
        elif rol == 'empleado':
            return redirect('app_empleado:dashboard')
    except Exception:
        pass
    # Sin perfil o rol desconocido → seleccionar rol (nunca a /)
    return redirect('authentication:seleccionar_rol')


# ─── LOGOUT ───────────────────────────────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('core:home')


# ─── SELECCIÓN DE ROL (usuarios nuevos via Google) ───────────────────────────

@login_required
def seleccionar_rol(request):
    """
    Vista exclusiva para usuarios que acaban de registrarse con Google
    y todavía no tienen perfil. Les permite elegir entre Padre o Docente.
    """
    # Si ya tiene perfil, no necesita estar aquí
    if hasattr(request.user, 'perfil'):
        return _redirigir_por_rol(request.user)

    if request.method == 'POST':
        rol = request.POST.get('rol', '')

        if rol not in ('padre', 'docente'):
            messages.error(request, 'Por favor selecciona un rol válido.')
            return render(request, 'authentication/seleccionar_rol.html')

        # Crear perfil + modelo específico según el rol elegido
        if rol == 'padre':
            perfil = Perfil.objects.create(user=request.user, rol='padre')
            Padre.objects.create(perfil=perfil)
        elif rol == 'docente':
            perfil = Perfil.objects.create(user=request.user, rol='docente')
            Docente.objects.create(perfil=perfil)

        # Limpiar marcas de sesión
        request.session.pop('google_nuevo_usuario', None)
        request.session.pop('google_user_id', None)

        messages.success(request, f'¡Bienvenido! Tu cuenta ha sido creada como {perfil.get_rol_display()}.')

        # Refrescar el user desde la BD para que el caché del ORM incluya el perfil recién creado
        request.user.refresh_from_db()
        return _redirigir_por_rol(request.user)

    # GET → mostrar pantalla de selección
    # No bloqueamos si no hay marca de sesión: puede que el usuario
    # llegue aquí de forma legítima (refresh después de Google login)
    return render(request, 'authentication/seleccionar_rol.html')


# ─── REGISTRO PADRE ───────────────────────────────────────────────────────────

def registro_padre(request):
    """Los padres pueden registrarse por su cuenta."""
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil'):
            return _redirigir_por_rol(request.user)
        return redirect('authentication:seleccionar_rol')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        telefono   = request.POST.get('telefono', '').strip()
        documento  = request.POST.get('documento', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        errores = []
        if not all([first_name, last_name, email, password1]):
            errores.append('Nombre, apellido, correo y contraseña son obligatorios.')
        if password1 != password2:
            errores.append('Las contraseñas no coinciden.')
        if len(password1) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if email and User.objects.filter(email=email).exists():
            errores.append('Ya existe una cuenta con ese correo.')

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            username = generar_username(email)
            user = User.objects.create_user(
                username=username,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            perfil = Perfil.objects.create(user=user, rol='padre', telefono=telefono)
            Padre.objects.create(perfil=perfil, documento=documento)
            messages.success(
                request,
                '¡Cuenta creada! Ya puedes iniciar sesión con tu correo.'
            )
            return redirect('authentication:login')

    return render(request, 'authentication/registro_padre.html')


# ─── REGISTRO DOCENTE ─────────────────────────────────────────────────────────

def registro_docente(request):
    """Los docentes pueden registrarse por su cuenta."""
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil'):
            return _redirigir_por_rol(request.user)
        return redirect('authentication:seleccionar_rol')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip().lower()
        telefono   = request.POST.get('telefono', '').strip()
        documento  = request.POST.get('documento', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        errores = []
        if not all([first_name, last_name, email, password1]):
            errores.append('Nombre, apellido, correo y contraseña son obligatorios.')
        if password1 != password2:
            errores.append('Las contraseñas no coinciden.')
        if len(password1) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if email and User.objects.filter(email=email).exists():
            errores.append('Ya existe una cuenta con ese correo.')

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            username = generar_username(email)
            user = User.objects.create_user(
                username=username,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            perfil = Perfil.objects.create(user=user, rol='docente', telefono=telefono)
            Docente.objects.create(perfil=perfil, documento=documento)
            messages.success(
                request,
                '¡Cuenta creada! Ya puedes iniciar sesión con tu correo.'
            )
            return redirect('authentication:login')

    return render(request, 'authentication/registro_docente.html')