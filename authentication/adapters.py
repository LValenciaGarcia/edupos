from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.urls import reverse
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class RolSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Antes del login social: evitamos el formulario de signup y manejamos
        la asociación con usuarios existentes por email.
        """
        logger.debug('pre_social_login ejecutándose')

        # Si ya existe la cuenta social, no intervenir
        if sociallogin.is_existing:
            logger.debug('Cuenta social ya existente, login normal')
            return

        # Obtener email del usuario social (ya debería estar en sociallogin.user.email)
        email = sociallogin.user.email
        if not email:
            # Fallback: extraer de extra_data
            email = sociallogin.account.extra_data.get('email')

        if not email:
            logger.debug('No se pudo obtener email, se requerirá formulario')
            return

        # Buscar si ya existe un usuario con ese email
        try:
            existing_user = User.objects.get(email=email)
        except User.DoesNotExist:
            # El flujo normal de allauth (con populate_user) creará el usuario
            # No hacemos nada especial aquí, dejamos que allauth continúe
            return

        # Si el usuario existe, asociamos la cuenta social a ese usuario
        sociallogin.connect(request, existing_user)
        # Forzamos que el proceso sea 'login' y no 'signup'
        sociallogin.state['process'] = 'login'

    def populate_user(self, request, sociallogin, data):
        """
        Llena el usuario con datos del proveedor.
        """
        user = super().populate_user(request, sociallogin, data)

        email = data.get('email')
        if email:
            user.email = email

        if not user.username:
            base_username = email.split('@')[0] if email else 'usuario'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user.username = username

        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if not hasattr(user, 'perfil'):
            request.session['google_nuevo_usuario'] = True
            request.session['google_user_id'] = user.pk
        return user

    def get_login_redirect_url(self, request):
        user = request.user
        if request.session.get('google_nuevo_usuario'):
            return reverse('authentication:seleccionar_rol')
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
        return reverse('authentication:seleccionar_rol')