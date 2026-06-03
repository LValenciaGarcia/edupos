from django import template
import re

register = template.Library()


@register.filter(name='cloudinary_jpg')
def cloudinary_jpg(url):
    """Convierte URL de Cloudinary para forzar formato JPEG (soluciona .jfif/.avif en navegadores)."""
    if not url or 'res.cloudinary.com' not in str(url):
        return url
    # Inserta f_jpg,q_auto después de /upload/
    return re.sub(r'(/upload/)(v\d+/)?', r'\1f_jpg,q_auto/\2', str(url), count=1)


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
