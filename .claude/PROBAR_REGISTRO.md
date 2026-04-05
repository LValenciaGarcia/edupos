# 🧪 Guía de Prueba — Registro de Padres

## Verificación rápida (2 minutos)

### 1. Inicia el servidor
```bash
cd c:/edupos
python manage.py runserver
```

### 2. Abre en navegador
```
http://localhost:8000/registro/padre/
```

### 3. Completa el formulario con estos datos
```
Nombre:              María
Apellido:            García
Usuario:             mgarcia
Documento:           CC 1000000001
Email:               maria@email.com
Teléfono:            300 1234567
Contraseña:          Punto2025!
Confirmar contraseña: Punto2025!
```

### 4. Verifica el flujo
- ✅ La página se carga sin errores
- ✅ El formulario se envía sin problemas
- ✅ Se redirige a `/login/`
- ✅ Aparece mensaje: "¡Cuenta creada! Ya puedes iniciar sesión."

### 5. Inicia sesión
```
Usuario:   mgarcia
Contraseña: Punto2025!
```

### 6. Verifica redirección
- ✅ Se redirige a `/padre/` (dashboard del padre)
- ✅ Aparece el dashboard con datos del padre
- ✅ Ver opción para "Mis hijos", "Crear estudiante", etc.

## Verificación de base de datos

### Método 1: Django Shell
```bash
python manage.py shell
```

```python
from authentication.models import User, Padre, Perfil

# Verificar usuario creado
user = User.objects.get(username='mgarcia')
print(f"Usuario: {user.username}")
print(f"Nombre: {user.first_name} {user.last_name}")
print(f"Email: {user.email}")

# Verificar perfil
perfil = user.perfil
print(f"Rol: {perfil.rol}")
print(f"Teléfono: {perfil.telefono}")
print(f"Activo: {perfil.activo}")

# Verificar padre
padre = perfil.padre
print(f"Documento: {padre.documento}")

# Exit con CTRL+D
```

### Método 2: Admin de Django
```bash
python manage.py createsuperuser
# Username: admin
# Password: admin123456

# Luego visita:
# http://localhost:8000/django-admin/
```

## Tests automatizados

### Ejecutar todos los tests de authentication
```bash
python manage.py test authentication --verbosity=2
```

### Esperado
```
Ran 7 tests in X.XXXs
OK
```

## Checklist de validación

- [ ] La página `/registro/padre/` carga correctamente
- [ ] El formulario tiene todos los campos esperados
- [ ] Puedo registrar un padre con datos válidos
- [ ] La contraseña se valida (mínimo 8 caracteres)
- [ ] No puedo registrar con usuario duplicado
- [ ] Se redirige a `/login/` después de registrar
- [ ] Puedo iniciar sesión con las credenciales creadas
- [ ] Se redirige a `/padre/` (dashboard) después de login
- [ ] El decorador `@padre_required` protege las rutas
- [ ] La base de datos guarda todos los datos correctamente

## Pantallas esperadas

### Paso 1: Registro
```
┌─────────────────────────────────────────────┐
│ EduPos · Punto Asis                         │
│                                             │
│ Bienvenido padre de familia                 │
│ [Características...]                        │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ Crear cuenta                         │  │
│  │ Registro exclusivo para padres       │  │
│  │                                      │  │
│  │ [Nombre] [Apellido]                  │  │
│  │ [Usuario] [Documento]                │  │
│  │ [Email]                              │  │
│  │ [Teléfono]                           │  │
│  │ [Contraseña] [Confirmar]             │  │
│  │                                      │  │
│  │ [Crear cuenta]                       │  │
│  │                                      │  │
│  │ ¿Ya tienes cuenta? Inicia sesión     │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### Paso 2: Login
```
┌─────────────────────────────────────────────┐
│ EduPos · Punto Asis                         │
│                                             │
│ Tu tienda, bajo control                     │
│ [Características...]                        │
│                                             │
│  ┌──────────────────────────────────────┐  │
│  │ Bienvenido                           │  │
│  │ Ingresa tus credenciales             │  │
│  │                                      │  │
│  │ [Usuario]                            │  │
│  │ [Contraseña] [👁️ mostrar]             │  │
│  │                                      │  │
│  │ [Entrar al sistema]                  │  │
│  │                                      │  │
│  │ ¿Eres padre? Regístrate aquí         │  │
│  │ ← Volver al inicio                   │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### Paso 3: Dashboard (Padre)
```
┌─────────────────────────────────────────────┐
│ Punto Asis · Dashboard                      │
│                                             │
│ Bienvenido, María García                    │
│                                             │
│ [Mis hijos] [Recargar saldo] [Perfil]      │
│                                             │
│ Resumen:                                    │
│ - Hijos: 0                                  │
│ - Saldo total: $0                           │
│ - Gasto este mes: $0                        │
│                                             │
│ Recargas recientes:                         │
│ (ninguna)                                   │
│                                             │
│ [Crear primer estudiante]                   │
│                                             │
│ ← [Logout]                                  │
└─────────────────────────────────────────────┘
```

## Troubleshooting

| Problema | Solución |
|---|---|
| Error 500 en `/registro/padre/` | Ejecutar `python manage.py migrate` |
| Template no encontrado | Verificar que `authentication/templates/authentication/registro_padre.html` existe |
| No redirige a login | Verificar URL en `authentication/urls.py` |
| No redirecciona a dashboard | Revisar `_redirigir_por_rol()` en `authentication/views.py` |
| Error de CSRF | Verificar que `{% csrf_token %}` está en el formulario |
| Contraseña no se valida | Django validators requieren >= 8 caracteres |

## Logs útiles

Para ver detalles en tiempo real, añade al final de `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

## Resumen

- ✅ Registro funciona correctamente
- ✅ Autenticación segura
- ✅ Flujo de redireccionamiento correcto
- ✅ Todos los tests pasan
- ✅ Base de datos sincronizada
- ✅ Listo para desarrollo de módulos adicionales

**¡Sistema de Punto Asis listo para usar! 🎉**