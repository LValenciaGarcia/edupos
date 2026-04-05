from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Perfil, Padre


class RegistroPadreTestCase(TestCase):
    """Tests para el flujo de registro de padres."""

    def setUp(self):
        self.client = Client()
        self.registro_url = reverse('authentication:registro_padre')
        self.login_url = reverse('authentication:login')

    def test_pagina_registro_accesible(self):
        """GET /registro/padre/ debe retornar 200."""
        response = self.client.get(self.registro_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'authentication/registro_padre.html')

    def test_registrar_padre_valido(self):
        """Registrar un padre con datos válidos debe crear User + Perfil + Padre."""
        data = {
            'first_name': 'María',
            'last_name': 'García',
            'username': 'mgarcia',
            'email': 'maria@email.com',
            'telefono': '3001234567',
            'documento': 'CC 1000000001',
            'password1': 'Punto2025!',
            'password2': 'Punto2025!',
        }
        response = self.client.post(self.registro_url, data)

        # Debe redirigir a login
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.login_url)

        # Verificar que User fue creado
        user = User.objects.get(username='mgarcia')
        self.assertEqual(user.first_name, 'María')
        self.assertEqual(user.last_name, 'García')
        self.assertEqual(user.email, 'maria@email.com')

        # Verificar que Perfil fue creado con rol 'padre'
        perfil = Perfil.objects.get(user=user)
        self.assertEqual(perfil.rol, 'padre')
        self.assertEqual(perfil.telefono, '3001234567')
        self.assertTrue(perfil.activo)

        # Verificar que Padre fue creado
        padre = Padre.objects.get(perfil=perfil)
        self.assertEqual(padre.documento, 'CC 1000000001')

    def test_registrar_padre_contraseña_corta(self):
        """Registrar con contraseña < 8 caracteres debe fallar."""
        data = {
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'username': 'jperez',
            'password1': '123456',
            'password2': '123456',
        }
        response = self.client.post(self.registro_url, data)

        # Debe retornar 200 (no redirige si hay error)
        self.assertEqual(response.status_code, 200)

        # No debe crear User
        self.assertFalse(User.objects.filter(username='jperez').exists())

    def test_registrar_padre_contraseña_no_coincide(self):
        """Registrar con contraseñas no coincidentes debe fallar."""
        data = {
            'first_name': 'Juan',
            'last_name': 'Pérez',
            'username': 'jperez',
            'password1': 'Punto2025!',
            'password2': 'Punto2025@',
        }
        response = self.client.post(self.registro_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='jperez').exists())

    def test_registrar_padre_usuario_duplicado(self):
        """Registrar con usuario duplicado debe fallar."""
        # Crear primer usuario
        User.objects.create_user(username='mgarcia', password='pass123456')

        data = {
            'first_name': 'María',
            'last_name': 'García',
            'username': 'mgarcia',
            'password1': 'Punto2025!',
            'password2': 'Punto2025!',
        }
        response = self.client.post(self.registro_url, data)

        self.assertEqual(response.status_code, 200)
        # Solo debe existir un usuario con ese username
        self.assertEqual(User.objects.filter(username='mgarcia').count(), 1)

    def test_login_padre_registrado(self):
        """Login de padre registrado debe redirigir a app_padre:dashboard."""
        # Registrar padre
        data = {
            'first_name': 'María',
            'last_name': 'García',
            'username': 'mgarcia',
            'password1': 'Punto2025!',
            'password2': 'Punto2025!',
        }
        self.client.post(self.registro_url, data)

        # Login
        login_data = {
            'username': 'mgarcia',
            'password': 'Punto2025!',
        }
        response = self.client.post(self.login_url, login_data)

        # Debe redirigir a app_padre:dashboard
        self.assertRedirects(response, reverse('app_padre:dashboard'))

    def test_usuario_autenticado_en_registro(self):
        """Usuario autenticado visitando /registro/padre/ debe redirigir."""
        # Crear y registrar usuario
        data = {
            'first_name': 'María',
            'last_name': 'García',
            'username': 'mgarcia',
            'password1': 'Punto2025!',
            'password2': 'Punto2025!',
        }
        self.client.post(self.registro_url, data)

        # Login
        login_data = {
            'username': 'mgarcia',
            'password': 'Punto2025!',
        }
        self.client.post(self.login_url, login_data)

        # Visitar registro estando autenticado debe redirigir
        response = self.client.get(self.registro_url)
        self.assertEqual(response.status_code, 302)
