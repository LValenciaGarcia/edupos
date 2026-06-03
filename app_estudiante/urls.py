from django.urls import path
from . import views

app_name = 'app_estudiante'

urlpatterns = [
    path('',                              views.dashboard,         name='dashboard'),
    path('menu/',                         views.menu,              name='menu'),
    path('historial/',                    views.historial,         name='historial'),
    path('perfil/',                       views.perfil,            name='perfil'),
    path('estadisticas/',                 views.estadisticas,      name='estadisticas'),
    path('pedido/<int:pk>/cancelar/',     views.cancelar_pedido,   name='cancelar_pedido'),
    path('notificaciones/',               views.notificaciones,    name='notificaciones'),
    path('restricciones/',                views.mis_restricciones, name='mis_restricciones'),
    path('saldo/',                        views.mi_saldo,          name='mi_saldo'),
    path('recargar/',                     views.recargar_saldo,    name='recargar_saldo'),
    path('qr/',                           views.mi_qr,             name='mi_qr'),
]
