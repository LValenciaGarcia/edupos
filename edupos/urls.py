from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
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

urlpatterns = [
    path('sw.js', _sw),
    path('django-admin/', admin.site.urls),
    path('',              include('core.urls')),
    path('',              include('authentication.urls')),
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
