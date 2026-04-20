# Punto Asis — Cafetería Escolar

Django POS system for school cafeteria — Colegio San Francisco de Asís, Cali. Academic thesis project.

## Commands

```bash
python manage.py runserver        # Dev server on http://127.0.0.1:8000
python manage.py migrate          # Apply migrations
python manage.py createsuperuser  # Create admin user
pip install -r requirements.txt   # Install dependencies (Django, Pillow, openpyxl, reportlab)
```

## Architecture

**Apps and URL prefixes:**

| App | Prefix | Status |
|-----|--------|--------|
| `authentication` | `/login/`, `/registro/` | In progress |
| `core` | `/` | Complete |
| `app_admin` | `/admin-panel/` | In progress |
| `app_docente` | `/docente/` | In progress |
| `app_estudiante` | `/estudiante/` | In progress |
| `app_padre` | `/padre/` | In progress |

Django admin (superuser only): `/django-admin/`

## Role System

`authentication.Perfil` extends Django `User` with a `rol` field: `admin`, `padre`, `estudiante`, `docente`. Each role has a companion model with extended fields.

- Estudiante accounts are created by their Padre, not self-registered
- Docente supports fiado (credit) system: `limite_fiado` / `deuda_fiado` fields

## Custom Template Filter

`|miles` filter (Colombian thousands formatting) lives in `app_admin/templatetags/filtros.py`. Load with `{% load filtros %}` in any template that formats currency.

## Design Conventions

- **Base template:** `app_admin/templates/base_admin.html` — sidebar dark `#0f0f0e`, background cream `#f3f2ee`, CSS variables in `:root`
- **Accent colors by role:** docente = `#7c3aed` (purple); others follow base palette
- **Frontend libs (CDN):** Bootstrap Icons, Chart.js, FullCalendar, DM Serif Display + Inter fonts
- New apps must reuse the same sidebar/base design as existing apps

## Key Files

- `edupos/settings.py` — project settings (SQLite, DEBUG=True)
- `edupos/urls.py` — root URL conf
- `authentication/models.py` — Perfil, Padre, Estudiante, Docente models
- `app_admin/templatetags/filtros.py` — `|miles` filter

## Media Uploads

Models with image/file fields write to these `media/` subdirectories:
`ingredientes/`, `perfiles/`, `productos/`, `proveedores/`, `recargas/`
