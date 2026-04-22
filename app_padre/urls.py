from django.urls import path
from . import views

app_name = 'app_padre'

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────────────────
    path('',                                        views.dashboard,            name='dashboard'),

    # ── Hijos ──────────────────────────────────────────────────────────────
    path('hijos/',                                  views.hijos,                name='hijos'),
    path('hijos/nuevo/',                            views.crear_estudiante,     name='crear_estudiante'),

    # ── Controles por hijo ─────────────────────────────────────────────────
    path('hijos/<int:pk>/recargar/',                views.recargar_saldo,       name='recargar_saldo'),
    path('hijos/<int:pk>/limites/',                 views.limites,              name='limites'),
    path('hijos/<int:pk>/restricciones/',           views.restricciones,        name='restricciones'),
    path('hijos/<int:pk>/horarios/',                views.horarios,             name='horarios'),
    path('hijos/<int:pk>/pedir/',                   views.pedido_padre,         name='pedido_padre'),
    path('hijos/<int:pk>/programados/',             views.pedidos_programados,  name='pedidos_programados'),
    path('hijos/<int:pk>/alergias/',                views.alergias,             name='alergias'),

    # ── Cafetería ──────────────────────────────────────────────────────────
    path('menu/',                                   views.menu,                 name='menu'),
    path('historial/',                              views.historial,            name='historial'),
    path('historial/exportar/',                     views.exportar_csv,         name='exportar_csv'),

    # ── Estadísticas ───────────────────────────────────────────────────────
    path('estadisticas/',                           views.estadisticas,         name='estadisticas'),

    # ── Notificaciones ─────────────────────────────────────────────────────
    path('notificaciones/',                         views.notificaciones,       name='notificaciones'),
    path('api/notificaciones/',                     views.api_notificaciones,   name='api_notificaciones'),

    # ── IA APIs ────────────────────────────────────────────────────────────
    path('api/sugerir-alergia/',                    views.api_sugerir_alergia,  name='api_sugerir_alergia'),

    # ── Saldo del padre ────────────────────────────────────────────────────
    path('saldo/',                                  views.saldo_padre,          name='saldo_padre'),

    # ── Perfil ─────────────────────────────────────────────────────────────
    path('perfil/',                                 views.perfil,               name='perfil'),
]
