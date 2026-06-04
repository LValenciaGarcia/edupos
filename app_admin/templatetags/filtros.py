from django import template
from django.conf import settings
import re

register = template.Library()


@register.filter(name='cloudinary_jpg')
def cloudinary_jpg(imagen_field):
    """
    Recibe el ImageField completo o su URL y devuelve una URL de Cloudinary
    con formato JPEG forzado. Funciona aunque el storage local devuelva rutas relativas.
    """
    if not imagen_field:
        return ''

    url = str(imagen_field)

    # Si ya es URL de Cloudinary, solo inserta la transformación
    if 'res.cloudinary.com' in url:
        return re.sub(r'(/upload/)(v\d+/)?', r'\1f_jpg,q_auto/\2', url, count=1)

    # Si es una ruta relativa o /media/..., construir URL de Cloudinary manualmente
    cloud_name = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME', '')
    if not cloud_name:
        # Sin Cloudinary (desarrollo): si llega el .name (ruta relativa sin /media/),
        # anteponer MEDIA_URL para que la imagen resuelva localmente.
        if url.startswith(('http://', 'https://', '/')):
            return url
        return f'{settings.MEDIA_URL}{url}'

    # Obtener solo el name del campo (sin /media/ prefix)
    name = url
    for prefix in ('/media/', 'media/'):
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    # Quitar extensión para el public_id
    public_id = re.sub(r'\.[^.]+$', '', name)

    return f'https://res.cloudinary.com/{cloud_name}/image/upload/f_jpg,q_auto/media/{public_id}'


@register.filter(name='miles')
def miles(value):
    """1500000 → 1.500.000 (formato colombiano, sin decimales)."""
    try:
        return '{:,.0f}'.format(float(value)).replace(',', '.')
    except (ValueError, TypeError):
        return value


@register.filter(name='pesos')
def pesos(value):
    """1500000 → $1.500.000"""
    try:
        formatted = '{:,.0f}'.format(float(value)).replace(',', '.')
        return f'${formatted}'
    except (ValueError, TypeError):
        return f'${value}'
