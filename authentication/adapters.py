from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse


class RolSocialAccountAdapter(DefaultSocialAccountAdapter):

    def save_user(self, request, sociallogin, form=None):
        """
        Guarda el usuario. Si es nuevo (sin perfil), marca la sesión.
        """
        user = super().save_user(request, sociallogin, form)
        if not hasattr(user, 'perfil'):
            request.session['google_nuevo_usuario'] = True
            request.session['google_user_id'] = user.pk
        return user

    def get_login_redirect_url(self, request):
        """
        Allauth llama este método para decidir el destino post-login.
        """
        user = request.user

        # Usuario nuevo sin perfil → elegir rol
        if request.session.get('google_nuevo_usuario'):
            return reverse('authentication:seleccionar_rol')

        # Usuario existente → su dashboard
        return _url_por_rol(user)


def _url_por_rol(user):
    try:
        rol = user.perfil.rol
        rutas = {
            'admin':      'app_admin:dashboard',
            'padre':      'app_padre:dashboard',
            'estudiante': 'app_estudiante:dashboard',
            'docente':    'app_docente:dashboard',
            'empleado':   'app_empleado:dashboard',
        }
        return reverse(rutas.get(rol, 'core:home'))
    except Exception:
        # Sin perfil: fallback seguro siempre a seleccionar_rol
        return reverse('authentication:seleccionar_rol')