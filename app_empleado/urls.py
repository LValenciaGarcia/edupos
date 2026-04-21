from django.urls import path
from . import views

app_name = 'app_empleado'

urlpatterns = [
    path('',                        views.dashboard,          name='dashboard'),
    # Caja / POS
    path('caja/',                   views.caja,               name='caja'),
    path('caja/venta/',             views.procesar_venta,     name='procesar_venta'),
    path('caja/cliente/',           views.buscar_cliente,     name='buscar_cliente'),
    # Turno
    path('turno/',                  views.turno,              name='turno'),
    # Ventas & Anulación
    path('ventas/',                 views.ventas,             name='ventas'),
    path('ventas/anular/',          views.anular_venta,       name='anular_venta'),
    # Inventario (lectura)
    path('inventario/',             views.inventario_empleado, name='inventario'),
    # Clientes (historial)
    path('clientes/',               views.historial_cliente,  name='clientes'),
    # Perfil
    path('perfil/',                 views.perfil,             name='perfil'),
]
