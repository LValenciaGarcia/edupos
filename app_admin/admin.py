from django.contrib import admin
from .models import (
    Alergeno, Proveedor, Categoria, Ingrediente, Producto,
    RecetaIngrediente, CompraProveedor, DetalleCompra,
    Pedido, DetallePedido, Insumo, MovimientoInsumo,
    MovimientoIngrediente, MovimientoInventario, PerfilAdmin,
)


@admin.register(Alergeno)
class AlergenoAdmin(admin.ModelAdmin):
    list_display  = ('codigo', 'get_codigo_display', 'icono')
    ordering      = ('codigo',)


@admin.register(Ingrediente)
class IngredienteAdmin(admin.ModelAdmin):
    list_display      = ('nombre', 'stock_unidades', 'unidad_compra', 'contenido_por_unidad', 'unidad_base', 'precio_compra', 'stock_minimo')
    list_filter       = ('unidad_base', 'alergenos')
    search_fields     = ('nombre',)
    filter_horizontal = ('alergenos',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'categoria', 'precio_venta', 'disponible')
    list_filter   = ('categoria', 'disponible')
    search_fields = ('nombre',)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'nit', 'contacto', 'telefono')
    search_fields = ('nombre', 'nit')


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activa')


@admin.register(RecetaIngrediente)
class RecetaIngredienteAdmin(admin.ModelAdmin):
    list_display  = ('producto', 'ingrediente', 'cantidad')
    list_filter   = ('producto',)


class DetalleCompraInline(admin.TabularInline):
    model  = DetalleCompra
    extra  = 1


@admin.register(CompraProveedor)
class CompraProveedorAdmin(admin.ModelAdmin):
    list_display = ('proveedor', 'fecha', 'total')
    inlines      = [DetalleCompraInline]


class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display  = ('ticket', 'estudiante', 'estado', 'total', 'fecha_pedido')
    list_filter   = ('estado',)
    search_fields = ('ticket',)
    inlines       = [DetallePedidoInline]


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display  = ('nombre', 'unidad', 'stock', 'stock_minimo')
    search_fields = ('nombre',)


admin.site.register(MovimientoIngrediente)
admin.site.register(MovimientoInventario)
admin.site.register(MovimientoInsumo)
admin.site.register(PerfilAdmin)
