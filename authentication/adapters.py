from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import IntegrityError
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

class RolSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Antes del login social: evitamos el formulario de signup y manejamos
        la asociación con usuarios existentes por email.
        """
        print(">>> pre_social_login ejecutándose")
        
        # Si ya existe la cuenta social, no intervenir
        if sociallogin.is_existing:
            print(">>> Cuenta social ya existente, login normal")
            return
        
        # Obtener email del usuario social (ya debería estar en sociallogin.user.email)
        email = sociallogin.user.email
        if not email:
            # Fallback: extraer de extra_data
            email = sociallogin.account.extra_data.get('email')
        
        if not email:
            print(">>> No se pudo obtener email, se requerirá formulario")
            return
        
        print(f">>> Email obtenido: {email}")
        
        # Buscar si ya existe un usuario con ese email
        try:
            existing_user = User.objects.get(email=email)
            print(f">>> Usuario existente encontrado: {existing_user.username}")
        except User.DoesNotExist:
            print(">>> No existe usuario con ese email, se creará uno nuevo")
            # El flujo normal de allauth (con populate_user) creará el usuario
            # No hacemos nada especial aquí, dejamos que allauth continúe
            return
        
        # Si el usuario existe, asociamos la cuenta social a ese usuario
        sociallogin.connect(request, existing_user)
        print(">>> Cuenta social conectada al usuario existente")
        # Forzamos que el proceso sea 'login' y no 'signup'
        sociallogin.state['process'] = 'login'

    def populate_user(self, request, sociallogin, data):
        """
        Llena el usuario con datos del proveedor.
        """
        print(">>> populate_user ejecutándose")
        user = super().populate_user(request, sociallogin, data)
        
        email = data.get('email')
        if email:
            user.email = email
            print(f">>> Email asignado: {email}")
        
        if not user.username:
            base_username = email.split('@')[0] if email else 'usuario'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user.username = username
            print(f">>> Username generado: {user.username}")
        
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