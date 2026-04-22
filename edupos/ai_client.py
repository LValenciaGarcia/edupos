import os
import anthropic

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    """Devuelve el cliente Anthropic (singleton por proceso)."""
    global _client
    if _client is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            raise RuntimeError(
                'ANTHROPIC_API_KEY no está configurada. '
                'Agrégala en el archivo .env del proyecto.'
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client
