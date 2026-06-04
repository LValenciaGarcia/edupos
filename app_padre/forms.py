from django import forms
from .models import RecargaSaldo, LimiteGasto, AlergiaEstudiante, RestriccionAlimento, HorarioCompra


class CrearEstudianteForm(forms.Form):
    first_name = forms.CharField(max_length=100, label='Nombre(s)')
    last_name  = forms.CharField(max_length=100, label='Apellido(s)')
    grado      = forms.CharField(max_length=20, label='Grado')
    codigo     = forms.CharField(max_length=20, required=False, label='Código estudiantil')
    password1  = forms.CharField(
        min_length=8, label='Contraseña',
        widget=forms.PasswordInput(),
    )
    password2  = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(),
    )

    def clean(self):
        data = super().clean()
        if data.get('password1') != data.get('password2'):
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return data


class RecargaSaldoForm(forms.ModelForm):
    class Meta:
        model  = RecargaSaldo
        fields = ['monto', 'comprobante', 'nota']
        widgets = {
            'nota': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        if monto <= 0:
            raise forms.ValidationError('El monto debe ser mayor a cero.')
        return monto


class LimiteGastoForm(forms.ModelForm):
    class Meta:
        model  = LimiteGasto
        fields = ['tipo', 'monto', 'activo']

    def clean_monto(self):
        monto = self.cleaned_data['monto']
        if monto < 0:
            raise forms.ValidationError('El límite no puede ser negativo.')
        return monto


class AlergiaEstudianteForm(forms.ModelForm):
    class Meta:
        model  = AlergiaEstudiante
        fields = ['nombre', 'tipo', 'gravedad', 'notas']
        widgets = {
            'notas': forms.Textarea(attrs={'rows': 3}),
        }


class RestriccionAlimentoForm(forms.ModelForm):
    class Meta:
        model  = RestriccionAlimento
        fields = ['estudiante', 'producto', 'categoria', 'motivo']
        widgets = {
            'motivo': forms.Textarea(attrs={'rows': 2}),
        }


class HorarioCompraForm(forms.ModelForm):
    class Meta:
        model  = HorarioCompra
        fields = ['estudiante', 'nombre', 'hora_inicio', 'hora_fin', 'activo']
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin':    forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        data = super().clean()
        if data.get('hora_inicio') and data.get('hora_fin'):
            if data['hora_inicio'] >= data['hora_fin']:
                raise forms.ValidationError('La hora de inicio debe ser anterior a la hora de fin.')
        return data
