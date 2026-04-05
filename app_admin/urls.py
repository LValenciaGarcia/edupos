from django.urls import path
from . import views

app_name = 'app_admin'

urlpatterns = [
    # ── Dashboard ──────────────────────────────────────────────────────────
    path('',                                    views.dashboard,                name='dashboard'),

    # ── Productos ──────────────────────────────────────────────────────────
    path('productos/',                          views.productos,                name='productos'),
    path('productos/nuevo/',                    views.producto_nuevo,           name='producto_nuevo'),
    path('productos/<int:pk>/editar/',          views.producto_editar,          name='producto_editar'),
    path('productos/<int:pk>/eliminar/',        views.producto_eliminar,        name='producto_eliminar'),
    path('productos/<int:pk>/toggle/',          views.producto_toggle,          name='producto_toggle'),

    # ── Inventario ─────────────────────────────────────────────────────────
    path('inventario/',                         views.inventario,               name='inventario'),
    path('inventario/ajuste/<int:pk>/',         views.inventario_ajuste,        name='inventario_ajuste'),
    path('inventario/<int:pk>/historial/',      views.inventario_historial,     name='inventario_historial'),

    # ── Ingredientes ───────────────────────────────────────────────────────
    path('inventario/ingredientes/',            views.ingredientes,             name='ingredientes'),
    path('inventario/ingredientes/nuevo/',      views.ingrediente_nuevo,        name='ingrediente_nuevo'),
    path('inventario/ingredientes/<int:pk>/editar/',  views.ingrediente_editar, name='ingrediente_editar'),
    path('inventario/ingredientes/<int:pk>/ajuste/',  views.ingrediente_ajuste, name='ingrediente_ajuste'),
    path('inventario/ingredientes/<int:pk>/historial/', views.ingrediente_historial, name='ingrediente_historial'),

    # ── Entrada unificada de stock (vincula proveedor automáticamente) ─────
    path('inventario/entrada/',                 views.entrada_stock,            name='entrada_stock'),
    path('inventario/entrada/<int:pk>/',        views.entrada_stock,            name='entrada_stock_producto'),

    # ── Salida de stock ────────────────────────────────────────────────────
    path('inventario/salida/',                  views.salida_stock,             name='salida_stock'),

    # ── Eliminar ingrediente (soft-delete) ────────────────────────────────
    path('inventario/ingredientes/<int:pk>/eliminar/', views.ingrediente_eliminar, name='ingrediente_eliminar'),

    # ── Historial unificado ────────────────────────────────────────────────
    path('historial/',                          views.historial,                name='historial'),
    path('historial/api/',                      views.historial_api,            name='historial_api'),

    # ── Calendario de movimientos ──────────────────────────────────────────
    path('calendario/',                         views.calendario,               name='calendario'),
    path('calendario/api/',                     views.calendario_api,           name='calendario_api'),

    # ── Proveedores ────────────────────────────────────────────────────────
    path('proveedores/',                        views.proveedores,              name='proveedores'),
    path('proveedores/nuevo/',                  views.proveedor_nuevo,          name='proveedor_nuevo'),
    path('proveedores/<int:pk>/editar/',        views.proveedor_editar,         name='proveedor_editar'),
    path('proveedores/<int:pk>/compras/',       views.proveedor_compras,        name='proveedor_compras'),
    path('proveedores/<int:pk>/stats/',         views.proveedor_stats,          name='proveedor_stats'),
    path('compras/nueva/',                      views.compra_nueva,             name='compra_nueva'),
    path('compras/nueva/<int:prov_pk>/',        views.compra_nueva,             name='compra_nueva_proveedor'),

    # ── Pedidos ────────────────────────────────────────────────────────────
    path('pedidos/',                            views.pedidos,                  name='pedidos'),
    path('pedidos/<int:pk>/',                   views.pedido_detalle,           name='pedido_detalle'),
    path('pedidos/<int:pk>/estado/',            views.pedido_estado,            name='pedido_estado'),

    # ── Usuarios ───────────────────────────────────────────────────────────
    path('usuarios/',                           views.usuarios,                 name='usuarios'),
    path('usuarios/<int:pk>/toggle/',           views.usuario_toggle,           name='usuario_toggle'),
    path('usuarios/<int:pk>/',                  views.usuario_detalle,          name='usuario_detalle'),

    # ── Estadísticas ───────────────────────────────────────────────────────
    path('estadisticas/',                       views.estadisticas,             name='estadisticas'),
    path('estadisticas/api/ventas/',            views.api_ventas,               name='api_ventas'),
    path('estadisticas/api/categorias/',        views.api_categorias,           name='api_categorias'),
    path('estadisticas/api/productos/',         views.api_productos_top,        name='api_productos_top'),

    # ── Exportar ───────────────────────────────────────────────────────────
    path('inventario/exportar/excel/',          views.exportar_excel,           name='exportar_excel'),
    path('inventario/exportar/pdf/',            views.exportar_pdf,             name='exportar_pdf'),

    # ── Perfil y Configuración ─────────────────────────────────────────────
    path('perfil/',                             views.perfil,                   name='perfil'),
    path('configuracion/',                      views.configuracion,            name='configuracion'),

    # ── Alertas API ────────────────────────────────────────────────────────
    path('api/alertas/',                        views.api_alertas,              name='api_alertas'),
]
