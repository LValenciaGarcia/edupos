from django import forms
from django.contrib.auth.models import User


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.TextInput(attrs={'placeholder': 'correo@gmail.com', 'autofocus': True, 'type': 'email'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Contraseña'}),
    )


class RegistroBaseForm(forms.Form):
    first_name = forms.CharField(max_length=100, label='Nombre(s)')
    last_name  = forms.CharField(max_length=100, label='Apellido(s)')
    email      = forms.EmailField(required=False, label='Correo electrónico')
    telefono   = forms.CharField(max_length=15, required=False, label='Teléfono')
    documento  = forms.CharField(max_length=20, required=False, label='N° Documento')
    password1  = forms.CharField(
        min_length=8, label='Contraseña',
        widget=forms.PasswordInput(),
    )
    password2  = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(),
    )

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con ese correo.')
        return email

    def clean(self):
        data = super().clean()
        if data.get('password1') and data.get('password2'):
            if data['password1'] != data['password2']:
                raise forms.ValidationError('Las contraseñas no coinciden.')
        return data


class RegistroPadreForm(RegistroBaseForm):
    pass


class RegistroDocenteForm(RegistroBaseForm):
    materia = forms.CharField(max_length=100, required=False, label='Área / Materia')
