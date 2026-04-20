from django import template

register = template.Library()


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
