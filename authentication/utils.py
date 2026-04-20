import unicodedata
import re
from django.contrib.auth.models import User


def _normalizar(s: str) -> str:
    """Quita tildes y caracteres no alfanuméricos, devuelve a-z0-9."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', s.lower())


def generar_username(first_name: str, last_name: str) -> str:
    """Genera un username único con formato nombre.apellido."""
    base     = f"{_normalizar(first_name)}.{_normalizar(last_name)}"
    username = base
    counter  = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username
