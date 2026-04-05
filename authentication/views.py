from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Perfil, Padre


# ─── LOGIN ────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return _redirigir_por_rol(request.user)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Verificar que la cuenta esté activa
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
            messages.error(request, 'Usuario o contraseña incorrectos.')

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
        # elif rol == 'profesor':
        #     return redirect('app_profesor:dashboard')
    except Perfil.DoesNotExist:
        pass
    return redirect('core:home')


# ─── LOGOUT ───────────────────────────────────────────────────────────────────

def logout_view(request):
    logout(request)
    return redirect('core:home')


# ─── REGISTRO PADRE ───────────────────────────────────────────────────────────

def registro_padre(request):
    """Solo los padres pueden registrarse por su cuenta."""
    if request.user.is_authenticated:
        return _redirigir_por_rol(request.user)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        username   = request.POST.get('username', '').strip()
        email      = request.POST.get('email', '').strip()
        telefono   = request.POST.get('telefono', '').strip()
        documento  = request.POST.get('documento', '').strip()
        password1  = request.POST.get('password1', '')
        password2  = request.POST.get('password2', '')

        # Validaciones
        errores = []
        if not all([first_name, last_name, username, password1]):
            errores.append('Nombre, apellido, usuario y contraseña son obligatorios.')
        if password1 != password2:
            errores.append('Las contraseñas no coinciden.')
        if len(password1) < 8:
            errores.append('La contraseña debe tener al menos 8 caracteres.')
        if User.objects.filter(username=username).exists():
            errores.append('Ese nombre de usuario ya está en uso.')
        if email and User.objects.filter(email=email).exists():
            errores.append('Ya existe una cuenta con ese correo.')

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            user = User.objects.create_user(
                username=username,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
            perfil = Perfil.objects.create(user=user, rol='padre', telefono=telefono)
            Padre.objects.create(perfil=perfil, documento=documento)
            messages.success(request, '¡Cuenta creada! Ya puedes iniciar sesión.')
            return redirect('authentication:login')

    return render(request, 'authentication/registro_padre.html')
