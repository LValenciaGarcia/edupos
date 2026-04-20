import os
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_SIZE_MB = 5


def validate_image(file):
    """Valida extensión, tamaño y firma de bytes de un archivo de imagen."""
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f'Formato no permitido ({ext}). Usa: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}.'
        )

    max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file.size > max_bytes:
        raise ValidationError(f'La imagen no puede superar {MAX_IMAGE_SIZE_MB} MB.')

    # Verificar firma de bytes (magic bytes) con Pillow
    try:
        from PIL import Image
        img = Image.open(file)
        img.verify()           # Lanza excepción si el archivo está corrupto o es falso
        file.seek(0)           # Volver al inicio para que Django lo guarde correctamente
    except Exception:
        raise ValidationError('El archivo no es una imagen válida.')
