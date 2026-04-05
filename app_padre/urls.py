from django.urls import path
from . import views

app_name = 'app_padre'

urlpatterns = [
    path('',                          views.dashboard,         name='dashboard'),
    path('hijos/',                    views.hijos,             name='hijos'),
    path('hijos/nuevo/',              views.crear_estudiante,  name='crear_estudiante'),
    path('hijos/<int:pk>/recargar/',  views.recargar_saldo,    name='recargar_saldo'),
    path('menu/',                     views.menu,              name='menu'),
    path('historial/',                views.historial,         name='historial'),
    path('perfil/',                   views.perfil,            name='perfil'),
]
