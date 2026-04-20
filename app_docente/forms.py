from django import forms
from .models import RecargaDocente, PedidoProgramadoDocente, ReseñaProducto


class RecargaDocenteForm(forms.ModelForm):
    class Meta:
        model  = RecargaDocente
        fields = ['monto', 'comprobante', 'nota']
        widgets = {
            'nota': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        if monto <= 0:
            raise forms.ValidationError('El monto debe ser mayor a cero.')
        return monto


class PedidoProgramadoDocenteForm(forms.ModelForm):
    class Meta:
        model  = PedidoProgramadoDocente
        fields = ['fecha_entrega', 'hora_entrega', 'tipo_pago', 'nota']
        widgets = {
            'fecha_entrega': forms.DateInput(attrs={'type': 'date'}),
            'hora_entrega':  forms.TimeInput(attrs={'type': 'time'}),
            'nota':          forms.Textarea(attrs={'rows': 2}),
        }

    def clean_fecha_entrega(self):
        from datetime import date
        fecha = self.cleaned_data['fecha_entrega']
        if fecha < date.today():
            raise forms.ValidationError('La fecha de entrega no puede ser en el pasado.')
        return fecha


class ReseñaProductoForm(forms.ModelForm):
    class Meta:
        model  = ReseñaProducto
        fields = ['calificacion', 'comentario']
        widgets = {
            'comentario': forms.Textarea(attrs={'rows': 3, 'maxlength': 500}),
        }
