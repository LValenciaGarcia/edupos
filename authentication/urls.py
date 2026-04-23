from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/',              views.login_view,       name='login'),
    path('logout/',             views.logout_view,      name='logout'),
    path('registro/padre/',     views.registro_padre,   name='registro_padre'),
    path('registro/docente/',   views.registro_docente, name='registro_docente'),
    path('seleccionar-rol/',    views.seleccionar_rol,  name='seleccionar_rol'),
]