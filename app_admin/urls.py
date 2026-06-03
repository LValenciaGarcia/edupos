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

    # ── Lotes de ingrediente ───────────────────────────────────────────────
    path('inventario/ingredientes/<int:pk>/lotes/',          views.lotes_ingrediente, name='lotes_ingrediente'),
    path('inventario/lotes/<int:pk>/eliminar/',              views.lote_eliminar,     name='lote_eliminar'),

    # ── Producción de productos elaborados ────────────────────────────────
    path('produccion/',                                      views.producciones,      name='producciones'),
    path('produccion/nueva/',                                views.produccion_nueva,  name='produccion_nueva'),

    # ── Historial unificado ────────────────────────────────────────────────
    path('historial/',                          views.historial,                name='historial'),
    path('historial/api/',                      views.historial_api,            name='historial_api'),

    # ── Calendario de movimientos ──────────────────────────────────────────
    path('calendario/',                              views.calendario,                      name='calendario'),
    path('calendario/api/',                          views.calendario_api,                  name='calendario_api'),
    path('calendario/ical/<str:token>/',             views.calendario_ical,                 name='calendario_ical'),
    path('calendario/google/auth/',                  views.calendario_google_auth,          name='calendario_google_auth'),
    path('calendario/google/callback/',              views.calendario_google_callback,      name='calendario_google_callback'),
    path('calendario/google/sync/',                  views.calendario_google_sync,          name='calendario_google_sync'),
    path('calendario/google/disconnect/',            views.calendario_google_disconnect,    name='calendario_google_disconnect'),

    # ── Proveedores ────────────────────────────────────────────────────────
    path('proveedores/',                        views.proveedores,              name='proveedores'),
    path('proveedores/nuevo/',                  views.proveedor_nuevo,          name='proveedor_nuevo'),
    path('proveedores/<int:pk>/editar/',        views.proveedor_editar,         name='proveedor_editar'),
    path('proveedores/<int:pk>/compras/',       views.proveedor_compras,        name='proveedor_compras'),
    path('proveedores/<int:pk>/stats/',         views.proveedor_stats,          name='proveedor_stats'),
    path('proveedores/<int:pk>/eliminar/',     views.proveedor_eliminar,       name='proveedor_eliminar'),
    path('compras/nueva/',                      views.compra_nueva,             name='compra_nueva'),
    path('compras/nueva/<int:prov_pk>/',        views.compra_nueva,             name='compra_nueva_proveedor'),

    # ── Pedidos ────────────────────────────────────────────────────────────
    path('pedidos/',                            views.pedidos,                  name='pedidos'),
    path('pedidos/<int:pk>/',                   views.pedido_detalle,           name='pedido_detalle'),
    path('pedidos/<int:pk>/estado/',            views.pedido_estado,            name='pedido_estado'),
    path('pedidos/<int:pk>/factura/',           views.factura_vista,            name='factura_vista'),
    path('pedidos/<int:pk>/factura/pdf/',       views.factura_pdf,              name='factura_pdf'),

    # ── Pedidos Docentes ───────────────────────────────────────────────────
    path('pedidos-docentes/',                   views.pedidos_docentes,         name='pedidos_docentes'),
    path('pedidos-docentes/<int:pk>/',          views.pedido_docente_detalle,   name='pedido_docente_detalle'),
    path('pedidos-docentes/<int:pk>/estado/',   views.pedido_docente_estado,    name='pedido_docente_estado'),

    # ── Usuarios ───────────────────────────────────────────────────────────
    path('usuarios/',                           views.usuarios,                 name='usuarios'),
    path('usuarios/bulk/',                      views.usuario_bulk,             name='usuario_bulk'),
    path('usuarios/<int:pk>/toggle/',           views.usuario_toggle,           name='usuario_toggle'),
    path('usuarios/<int:pk>/eliminar/',         views.usuario_eliminar,         name='usuario_eliminar'),
    path('usuarios/<int:pk>/',                  views.usuario_detalle,          name='usuario_detalle'),

    # ── Estadísticas ───────────────────────────────────────────────────────
    path('estadisticas/',                       views.estadisticas,             name='estadisticas'),
    path('estadisticas/api/ventas/',            views.api_ventas,               name='api_ventas'),
    path('estadisticas/api/categorias/',        views.api_categorias,           name='api_categorias'),
    path('estadisticas/api/productos/',         views.api_productos_top,        name='api_productos_top'),

    # ── Exportar ───────────────────────────────────────────────────────────
    path('inventario/exportar/excel/',          views.exportar_excel,               name='exportar_excel'),
    path('inventario/exportar/pdf/',            views.exportar_pdf,                 name='exportar_pdf'),
    path('ingredientes/exportar/excel/',        views.exportar_ingredientes_excel,  name='exportar_ingredientes_excel'),
    path('ingredientes/exportar/pdf/',          views.exportar_ingredientes_pdf,    name='exportar_ingredientes_pdf'),

    # ── Perfil y Configuración ─────────────────────────────────────────────
    path('perfil/',                             views.perfil,                   name='perfil'),
    path('configuracion/',                      views.configuracion,            name='configuracion'),

    # ── Alertas API ────────────────────────────────────────────────────────
    path('api/alertas/',                        views.api_alertas,              name='api_alertas'),

    # ── IA APIs ────────────────────────────────────────────────────────────
    path('api/generar-descripcion/',            views.api_generar_descripcion,  name='api_generar_descripcion'),
    path('api/info-pago/<int:pk>/',             views.api_info_pago,            name='api_info_pago'),

    # ── Recargas (validación de comprobantes) ─────────────────────────────
    path('recargas/',                           views.recargas,                 name='recargas'),
    path('recargas/<str:tipo>/<int:pk>/resolver/', views.recarga_resolver,       name='recarga_resolver'),

    # ── Insumos ────────────────────────────────────────────────────────────
    path('insumos/',                            views.insumos,                  name='insumos'),
    path('insumos/nuevo/',                      views.insumo_nuevo,             name='insumo_nuevo'),
    path('insumos/<int:pk>/editar/',            views.insumo_editar,            name='insumo_editar'),
    path('insumos/<int:pk>/ajuste/',            views.insumo_ajuste,            name='insumo_ajuste'),
    path('insumos/<int:pk>/historial/',         views.insumo_historial,         name='insumo_historial'),
    path('insumos/<int:pk>/eliminar/',          views.insumo_eliminar,          name='insumo_eliminar'),
    path('insumos/<int:pk>/toggle/',            views.insumo_toggle,            name='insumo_toggle'),
    path('insumos/exportar/excel/',             views.exportar_insumos_excel,   name='exportar_insumos_excel'),
    path('insumos/exportar/pdf/',               views.exportar_insumos_pdf,     name='exportar_insumos_pdf'),

    # ── Acciones masivas ───────────────────────────────────────────────────
    path('productos/bulk/',                     views.producto_bulk,            name='producto_bulk'),
    path('ingredientes/bulk/',                  views.ingrediente_bulk,         name='ingrediente_bulk'),
    path('insumos/bulk/',                       views.insumo_bulk,              name='insumo_bulk'),

    # ── Empleados ──────────────────────────────────────────────────────────
    path('empleados/',                          views.empleados,                name='empleados'),
    path('empleados/nuevo/',                    views.empleado_nuevo,           name='empleado_nuevo'),
    path('empleados/<int:pk>/',                 views.empleado_detalle,         name='empleado_detalle'),
    path('empleados/<int:pk>/toggle/',          views.empleado_toggle,          name='empleado_toggle'),

    # ── Sedes ──────────────────────────────────────────────────────────────
    path('sedes/',                              views.sedes,                    name='sedes'),
    path('sedes/<int:pk>/toggle/',              views.sede_toggle,              name='sede_toggle'),

    # ── Carnets QR (impresión) ─────────────────────────────────────────────
    path('carnets/',                            views.carnets,           name='carnets'),
    path('carnets/pdf/',                        views.carnets_pdf,       name='carnets_pdf'),
]
