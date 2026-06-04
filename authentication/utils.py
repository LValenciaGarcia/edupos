import unicodedata
import re


def _normalizar(s: str) -> str:
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', s.lower())


def generar_username(email: str) -> str:
    """Username = email. Para padres/docentes que se registran con email."""
    return email.lower().strip()


def generar_username_estudiante(codigo: str) -> str:
    """Username técnico para estudiantes, basado en su código único."""
    return f"est.{codigo.lower().strip()}"