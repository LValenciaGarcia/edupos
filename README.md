# Punto Asis — EduPos
Sistema de gestión para cafetería escolar del Colegio San Francisco de Asís.

---

## Estructura del proyecto

```
edupos/
├── edupos/          → Configuración principal (settings, urls)
├── core/            → Landing page pública
├── authentication/  → Login, logout, registro de padres
├── app_admin/       → Módulo administrador (COMPLETO)
├── app_estudiante/  → Módulo estudiante (próximamente)
└── app_padre/       → Módulo padre (próximamente)
```

---

## Instalación paso a paso

### 1. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

### 2. Migraciones

```bash
python manage.py makemigrations authentication
python manage.py makemigrations app_admin
python manage.py migrate
```

### 3. Crear usuario administrador

```bash
python manage.py shell
```

Dentro del shell:

```python
from django.contrib.auth.models import User
from authentication.models import Perfil
from app_admin.models import Categoria

# Crear usuario admin
u = User.objects.create_superuser('admin', 'admin@puntoasis.com', 'admin1234')
u.first_name = 'Administrador'
u.last_name  = 'Punto Asis'
u.save()
Perfil.objects.create(user=u, rol='admin')

# Crear categorías base
Categoria.objects.create(nombre='desayuno', icono='🥐')
Categoria.objects.create(nombre='almuerzo', icono='🍽️')
Categoria.objects.create(nombre='snacks',   icono='🍿')
Categoria.objects.create(nombre='bebidas',  icono='🥤')

print("✅ Todo listo")
exit()
```

### 4. Correr el servidor

```bash
python manage.py runserver
```

### 5. Acceder

| URL | Descripción |
|-----|-------------|
| `http://127.0.0.1:8000/` | Landing page |
| `http://127.0.0.1:8000/login/` | Login |
| `http://127.0.0.1:8000/admin-panel/` | Panel administrador |
| `http://127.0.0.1:8000/registro/padre/` | Registro padres |

Credenciales por defecto: **admin / admin1234**

---

## Módulo Admin — Funcionalidades

- **Dashboard** → KPIs del día, gráfica de ventas, alertas de stock
- **Productos** → Grid estilo tienda, CRUD completo, productos simples y elaborados con receta
- **Inventario** → Control de stock, ajustes, historial, proyección de agotamiento
- **Ingredientes** → Materia prima para productos elaborados, stock propio
- **Pedidos** → Vista Kanban por estado, tickets `#PA-2025-XXXXX`, cambio de estado
- **Proveedores** → CRUD, historial de compras, actualización automática de stock
- **Usuarios** → Lista por rol, activar/desactivar cuentas, detalle por usuario
- **Estadísticas** → Gráficas de ventas, ganancia neta, margen, top productos, ventas por categoría

---

## Próximos módulos

- `app_estudiante` → Ver menú, hacer pedidos, ver historial y saldo
- `app_padre` → Ver hijos, recargar saldo, ver pedidos del hijo

---

## Correcciones v2

- **Sidebar** → icon-only minimalista, tooltip al hover, menú de usuario colapsable
- **Bootstrap Icons** → reemplaza todos los emojis en el módulo admin
- **Productos** → imagen con `aspect-ratio: 4/3` + `object-fit: cover` (siempre completa)
- **Botones** → solo icono, sin texto, animación hover
- **Tooltip Info** → panel flotante con datos completos del producto al hacer hover en (i)
- **Proveedor** → campos NIT y logo de empresa agregados
- **Formularios** → centrados con `max-width` + `margin: 0 auto`
- **Formato miles** → filtro `|miles` con separador de puntos colombiano (`1.500.000`)

### Nuevo comando de migración necesario
```bash
python manage.py makemigrations app_admin
python manage.py migrate
```
