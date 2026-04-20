from django import forms
from .models import Producto, Ingrediente, Proveedor, Categoria, Insumo


class ProductoForm(forms.ModelForm):
    class Meta:
        model  = Producto
        fields = [
            'tipo', 'categoria', 'nombre', 'descripcion',
            'precio_venta', 'precio_costo', 'proveedor',
            'stock', 'stock_minimo', 'imagen', 'disponible',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        data = super().clean()
        if data.get('tipo') == 'simple' and not data.get('precio_costo'):
            raise forms.ValidationError('Los productos simples deben tener precio de costo.')
        return data


class IngredienteForm(forms.ModelForm):
    class Meta:
        model  = Ingrediente
        fields = [
            'nombre', 'imagen', 'unidad', 'precio_unitario',
            'stock', 'stock_minimo', 'fecha_vencimiento', 'proveedor',
        ]
        widgets = {
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
        }


class ProveedorForm(forms.ModelForm):
    class Meta:
        model  = Proveedor
        fields = ['nombre', 'nit', 'contacto', 'telefono', 'email', 'direccion', 'logo']


class InsumoForm(forms.ModelForm):
    class Meta:
        model  = Insumo
        fields = [
            'nombre', 'categoria', 'unidad', 'imagen', 'descripcion',
            'stock', 'stock_minimo', 'precio_unitario', 'proveedor',
        ]
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 2}),
        }
