import unicodedata
import re
from django.contrib.auth.models import User


def _normalizar(s: str) -> str:
    """Quita tildes y caracteres no alfanuméricos, devuelve a-z0-9."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', s.lower())


def generar_username(email: str) -> str:
    """Username = email. Ya validado como único en el formulario."""
    return email.lower().strip()
