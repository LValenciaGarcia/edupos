from django.urls import path
from . import views

app_name = 'app_estudiante'

urlpatterns = [
    # Próximamente — Módulo Estudiante
    path('', views.dashboard, name='dashboard'),
]
