def notificaciones(request):
    """Expone `n_notif` (notificaciones sin leer) para el estudiante autenticado.

    Las Notificacion pertenecen al Padre; el estudiante visualiza las de su
    acudiente, así que el contador de la campana usa el mismo criterio que su
    página de notificaciones. Devuelve {} para cualquier otro tipo de usuario.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    try:
        perfil = user.perfil
        if perfil.rol != 'estudiante':
            return {}
        padre_id = perfil.estudiante.padre_id
    except Exception:
        return {}
    if not padre_id:
        return {'n_notif': 0}
    from app_padre.models import Notificacion
    return {'n_notif': Notificacion.objects.filter(padre_id=padre_id, leida=False).count()}
