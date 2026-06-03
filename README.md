# Punto Asis — EduPos

Sistema POS Django para cafetería escolar del Colegio San Francisco de Asís, Cali. Proyecto de tesis académica.

---

## 🚀 Quick Start

```bash
# Instalar dependencias
pip install -r requirements.txt

# Migraciones
python manage.py migrate

# Crear usuario admin
python manage.py createsuperuser

# Ejecutar servidor
python manage.py runserver
```

Acceso: `http://127.0.0.1:8000`

---

## 📁 Estructura del Proyecto

```
edupos/
├── authentication/      → Login, registro, modelo Perfil (rol-based)
├── core/               → Landing page pública
├── app_admin/          → Panel administrador (COMPLETO)
├── app_docente/        → Módulo docente (EN PROGRESO)
├── app_estudiante/     → Módulo estudiante (EN PROGRESO)
└── app_padre/          → Módulo padre (EN PROGRESO)
```

---

## 👥 Sistema de Roles

Cada usuario tiene un `Perfil` con un rol: `admin`, `docente`, `estudiante`, `padre`.

- **Estudiante:** Cuenta creada por su padre (no self-registered). Saldo de recargas.
- **Padre:** Crea estudiantes, recarga saldo, ve pedidos del hijo.
- **Docente:** Pide con su saldo propio recargado (no hay sistema de crédito).
- **Admin:** Panel de administración completo.

---

## 📋 Aplicaciones y URLs

| App | Prefijo | Estado |
|-----|---------|--------|
| `core` | `/` | Completo |
| `authentication` | `/login/`, `/registro/` | En progreso |
| `app_admin` | `/admin-panel/` | En progreso |
| `app_docente` | `/docente/` | En progreso |
| `app_estudiante` | `/estudiante/` | En progreso |
| `app_padre` | `/padre/` | En progreso |
| Django Admin | `/django-admin/` | Admin only |

---

## ⚙️ Módulo Admin — Funcionalidades

- **Dashboard** → KPIs del día, gráfica de ventas, alertas de stock
- **Productos** → CRUD completo, productos simples y elaborados con receta
- **Inventario** → Control de stock, ajustes, historial, proyección
- **Ingredientes** → Materia prima para productos elaborados
- **Pedidos** → Vista Kanban, tickets `#PA-XXXXX`, cambio de estado
- **Proveedores** → CRUD, historial de compras, actualización automática de stock
- **Usuarios** → Lista por rol, activar/desactivar, detalles
- **Estadísticas** → Gráficas de ventas, ganancia neta, margen, top productos

---

## 🎨 Convenciones de Diseño

- **Base template:** `app_admin/templates/base_admin.html`
- **Colores:** Sidebar `#0f0f0e` (oscuro), fondo `#f3f2ee` (crema)
- **Acentos por rol:** Docente = `#7c3aed` (morado)
- **Librerías:** Bootstrap Icons, Chart.js, FullCalendar, DM Serif Display + Inter fonts (CDN)
- **Filtro custom:** `|miles` → formato colombiano (`1.500.000`) en `app_admin/templatetags/filtros.py`

```django
{% load filtros %}
{{ valor|miles }}  {# 1500000 → 1.500.000 #}
```

---

## 📂 Media Uploads

Los modelos con campos de imagen/archivo escriben en `media/`:

```
media/
├── ingredientes/
├── perfiles/
├── productos/
├── proveedores/
└── recargas/
```

---

## 🔑 Archivos Clave

- `edupos/settings.py` → Configuración (SQLite, DEBUG=True)
- `edupos/urls.py` → Rutas principales
- `authentication/models.py` → Perfil, Padre, Estudiante, Docente
- `app_admin/templatetags/filtros.py` → Filtro `|miles`
- `app_admin/templates/base_admin.html` → Template base (sidebar, diseño)

---

## 📦 Dependencias

Instaladas en `requirements.txt`:

- Django
- Pillow (procesamiento de imágenes)
- openpyxl (exportar Excel)
- reportlab (reportes PDF)

---

## 🚧 Estado Actual (Abril 2026)

- ✅ `core` → Completo
- ✅ `app_admin` → Completo (+ v2 improvements pendientes)
- 🔄 `authentication` → En progreso (forms, validators)
- 🔄 `app_docente` → En progreso (models, views, forms)
- 🔄 `app_estudiante` → En progreso
- 🔄 `app_padre` → En progreso

---

