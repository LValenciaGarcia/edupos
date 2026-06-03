import hashlib
import hmac
import json
import logging

import mercadopago
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from app_padre.models import RecargaSaldo, RecargaPadre
from app_docente.models import RecargaDocente
from app_estudiante.models import RecargaEstudiante

logger = logging.getLogger(__name__)

_MODELOS = {
    'saldo':   RecargaSaldo,
    'padre':   RecargaPadre,
    'docente': RecargaDocente,
    'est':     RecargaEstudiante,
}

_ESTADOS_FALLO = {'rejected', 'cancelled', 'refunded', 'charged_back'}


def _verificar_firma_mp(request, payment_id: str) -> bool:
    """
    Valida la firma HMAC SHA256 del header `x-signature` enviada por MercadoPago.

    Doc: https://www.mercadopago.com/developers/es/docs/your-integrations/notifications/webhooks#editor_4
    Si MERCADOPAGO_WEBHOOK_SECRET no está configurado, se permite la entrada
    para no romper el flujo en desarrollo, pero se loguea como advertencia.
    """
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '')
    if not secret:
        logger.warning('MERCADOPAGO_WEBHOOK_SECRET no configurado: webhook acepta cualquier origen.')
        return True

    signature_header = request.headers.get('x-signature', '')
    request_id       = request.headers.get('x-request-id', '')
    if not signature_header or not request_id:
        return False

    parts = dict(p.strip().split('=', 1) for p in signature_header.split(',') if '=' in p)
    ts = parts.get('ts', '')
    v1 = parts.get('v1', '')
    if not ts or not v1:
        return False

    manifest = f'id:{payment_id};request-id:{request_id};ts:{ts};'
    digest = hmac.new(
        secret.encode('utf-8'),
        manifest.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, v1)


@csrf_exempt
def webhook(request):
    """Recibe notificaciones de pago de MercadoPago (IPN y Webhooks)."""
    payment_id = None

    # Formato IPN clásico: GET ?topic=payment&id=<id>
    if request.GET.get('topic') == 'payment':
        payment_id = request.GET.get('id')

    # Formato webhook moderno: POST con JSON {"type":"payment","data":{"id":"..."}}
    if not payment_id and request.method == 'POST' and request.body:
        try:
            data = json.loads(request.body)
            if data.get('type') == 'payment':
                payment_id = str(data['data']['id'])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    if not payment_id:
        return HttpResponse(status=200)

    if not _verificar_firma_mp(request, str(payment_id)):
        logger.warning('MP webhook con firma inválida (payment_id=%s)', payment_id)
        return HttpResponse(status=401)

    try:
        sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
        result = sdk.payment().get(payment_id)
        payment_data = result.get('response', {})
        status = payment_data.get('status')
        external_ref = payment_data.get('external_reference', '')

        if status == 'approved':
            _aprobar_recarga(external_ref, str(payment_id))
        elif status in _ESTADOS_FALLO:
            _rechazar_recarga(external_ref, str(payment_id))

    except Exception as e:
        logger.error('MP webhook error: %s', e)

    return HttpResponse(status=200)


def _aprobar_recarga(external_ref, payment_id):
    tipo, _, pk_str = external_ref.partition('-')
    if not pk_str.isdigit():
        return
    pk = int(pk_str)

    Model = _MODELOS.get(tipo)
    if not Model:
        return

    try:
        recarga = Model.objects.get(pk=pk, estado='pendiente')
        recarga.mp_payment_id = payment_id
        recarga.save(update_fields=['mp_payment_id'])
        recarga.aprobar()
        logger.info('Recarga %s-%s aprobada vía MP (payment_id=%s)', tipo, pk, payment_id)
    except Model.DoesNotExist:
        logger.warning('Recarga %s-%s no encontrada o ya procesada', tipo, pk)


def _rechazar_recarga(external_ref, payment_id=''):
    tipo, _, pk_str = external_ref.partition('-')
    if not pk_str.isdigit():
        return
    pk = int(pk_str)

    Model = _MODELOS.get(tipo)
    if not Model:
        return

    try:
        recarga = Model.objects.get(pk=pk, estado='pendiente')
        if payment_id:
            recarga.mp_payment_id = payment_id
            recarga.save(update_fields=['mp_payment_id'])
        recarga.rechazar(nota='Cancelado o rechazado por MercadoPago')
        logger.info('Recarga %s-%s rechazada vía MP (payment_id=%s)', tipo, pk, payment_id)
    except Model.DoesNotExist:
        logger.warning('Recarga %s-%s no encontrada o ya procesada', tipo, pk)


def pago_exitoso(request):
    return render(request, 'pagos/exitoso.html')


def pago_pendiente(request):
    return render(request, 'pagos/pendiente.html')


def pago_fallido(request):
    external_ref = request.GET.get('external_reference', '')
    payment_id = request.GET.get('payment_id') or request.GET.get('collection_id') or ''
    if external_ref:
        try:
            _rechazar_recarga(external_ref, str(payment_id))
        except Exception as e:
            logger.error('Error al rechazar recarga desde pago_fallido: %s', e)
    return render(request, 'pagos/fallido.html')
