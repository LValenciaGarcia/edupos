from django import forms
from .models import Producto, Ingrediente, LoteIngrediente, ProduccionElaborado, Proveedor, Categoria, Insumo


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
            'nombre', 'imagen', 'proveedor',
            'unidad_compra', 'contenido_por_unidad',
            'unidad_base', 'stock_minimo',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)
        self.fields['proveedor'].empty_label = '— Selecciona el proveedor principal —'


class LoteIngredienteForm(forms.ModelForm):
    class Meta:
        model  = LoteIngrediente
        fields = ['proveedor', 'unidades_compra', 'precio_compra', 'fecha_vencimiento', 'nota']
        widgets = {
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
            'nota': forms.TextInput(),
        }

    def __init__(self, *args, ingrediente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ingrediente = ingrediente
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)
        if ingrediente and ingrediente.proveedor_id:
            self.fields['proveedor'].initial = ingrediente.proveedor_id

    def save(self, commit=True):
        lote = super().save(commit=False)
        if self.ingrediente:
            lote.ingrediente = self.ingrediente
            cpd = float(self.ingrediente.contenido_por_unidad)
            cantidad_base = round(float(lote.unidades_compra) * cpd, 3)
            lote.cantidad_base = cantidad_base
            lote.cantidad_base_inicial = cantidad_base
        if commit:
            lote.save()
        return lote


class ProduccionForm(forms.ModelForm):
    class Meta:
        model  = ProduccionElaborado
        fields = ['producto', 'cantidad_producida', 'nota']
        widgets = {
            'nota': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(tipo='elaborado', disponible=True)
        self.fields['producto'].empty_label = '— Selecciona el producto —'


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
