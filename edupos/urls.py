from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
import os


def _sw(request):
    p = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    try:
        content = open(p).read()
    except FileNotFoundError:
        content = ''
    r = HttpResponse(content, content_type='application/javascript')
    r['Service-Worker-Allowed'] = '/'
    return r


def _home_o_dashboard(request):
    """
    Intercepta '/'.
    - Usuario autenticado con perfil  → su dashboard
    - Usuario autenticado sin perfil  → seleccionar rol
    - Usuario anónimo                 → home normal de core
    """
    if request.user.is_authenticated:
        if hasattr(request.user, 'perfil'):
            rol = request.user.perfil.rol
            rutas = {
                'admin':      'app_admin:dashboard',
                'padre':      'app_padre:dashboard',
                'estudiante': 'app_estudiante:dashboard',
                'docente':    'app_docente:dashboard',
                'empleado':   'app_empleado:dashboard',
            }
            nombre = rutas.get(rol)
            if nombre:
                return HttpResponseRedirect(reverse(nombre))
        return HttpResponseRedirect(reverse('authentication:seleccionar_rol'))

    # Anónimo → delegar a la vista home de core
    from core.views import home  # import local para evitar imports circulares
    return home(request)


urlpatterns = [
    path('sw.js', _sw),
    path('django-admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),   # ← allauth (Google OAuth)
    path('',          _home_o_dashboard),         # ← intercepta / antes que core
    path('',          include('core.urls')),       # ← resto de rutas de core
    path('',          include('authentication.urls')),
    path('admin-panel/',  include('app_admin.urls')),
    path('estudiante/',   include('app_estudiante.urls')),
    path('padre/',        include('app_padre.urls')),
    path('docente/',      include('app_docente.urls')),
    path('empleado/',     include('app_empleado.urls')),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)