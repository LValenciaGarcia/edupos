from django.urls import path
from . import views

app_name = 'app_docente'

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────────────────
    path('',                              views.dashboard,           name='dashboard'),

    # ── Menú / Pedir ───────────────────────────────────────────────────────
    path('menu/',                         views.menu,                name='menu'),
    path('pedir/',                        views.pedir,               name='pedir'),
    path('pedir/confirmar/',             views.confirmar_pedido,    name='confirmar_pedido'),

    # ── Pedidos grupales ───────────────────────────────────────────────────
    path('grupal/',                       views.pedidos_grupales,    name='pedidos_grupales'),
    path('grupal/crear/',                 views.crear_grupal,        name='crear_grupal'),
    path('grupal/<int:pk>/',              views.detalle_grupal,      name='detalle_grupal'),
    path('grupal/<int:pk>/unirse/',       views.unirse_grupal,       name='unirse_grupal'),
    path('grupal/<int:pk>/cerrar/',       views.cerrar_grupal,       name='cerrar_grupal'),

    # ── Pedidos programados ────────────────────────────────────────────────
    path('programados/',                  views.programados,         name='programados'),
    path('programados/nuevo/',            views.nuevo_programado,    name='nuevo_programado'),
    path('programados/<int:pk>/cancelar/', views.cancelar_programado, name='cancelar_programado'),
    path('api/programados/',              views.api_programados,     name='api_programados'),

    # ── Historial ──────────────────────────────────────────────────────────
    path('historial/',                    views.historial,           name='historial'),
    path('historial/exportar/',           views.exportar_csv,        name='exportar_csv'),

    # ── Estadísticas ───────────────────────────────────────────────────────
    path('estadisticas/',                 views.estadisticas,        name='estadisticas'),

    # ── Favoritos ──────────────────────────────────────────────────────────
    path('favoritos/',                    views.favoritos,           name='favoritos'),
    path('favoritos/toggle/<int:pk>/',    views.toggle_favorito,     name='toggle_favorito'),

    # ── Reseñas ────────────────────────────────────────────────────────────
    path('reseñas/guardar/<int:pk>/',     views.guardar_reseña,      name='guardar_reseña'),

    # ── Recarga de saldo ───────────────────────────────────────────────────
    path('recargar/',                     views.recargar_saldo,      name='recargar_saldo'),

    # ── Perfil ─────────────────────────────────────────────────────────────
    path('perfil/',                       views.perfil,              name='perfil'),

    # ── API Notificaciones ─────────────────────────────────────────────────
    path('api/notificaciones/',           views.api_notificaciones,  name='api_notificaciones'),
]
