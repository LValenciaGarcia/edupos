from django import template
from django.utils.formats import number_format

register = template.Library()

@register.filter(name='miles')
def miles(value):
    """
    Formatea un número con separador de miles (punto) y sin decimales.
    Ej: 1500000 → 1.500.000
    """
    try:
        value = float(value)
        # Formato colombiano: puntos para miles, sin decimales
        return '{:,.0f}'.format(value).replace(',', '.')
    except (ValueError, TypeError):
        return value


@register.filter(name='pesos')
def pesos(value):
    """
    Formatea como valor en pesos colombianos.
    Ej: 1500000 → $1.500.000
    """
    try:
        value = float(value)
        formatted = '{:,.0f}'.format(value).replace(',', '.')
        return f'${formatted}'
    except (ValueError, TypeError):
        return f'${value}'
