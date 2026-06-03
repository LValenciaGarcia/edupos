import mercadopago
from django.conf import settings


def crear_preferencia_mp(titulo, monto, external_reference):
    """
    Crea una preferencia de pago en MercadoPago y retorna el objeto response.
    external_reference debe tener formato: "saldo-{pk}", "padre-{pk}" o "docente-{pk}"
    """
    sdk = mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)
    site_url = settings.SITE_URL

    preference_data = {
        "items": [{
            "title": titulo,
            "quantity": 1,
            "currency_id": "COP",
            "unit_price": float(monto),
        }],
        "back_urls": {
            "success": f"{site_url}/pagos/exitoso/",
            "failure": f"{site_url}/pagos/fallido/",
            "pending": f"{site_url}/pagos/pendiente/",
        },
        "auto_return": "approved",
        "notification_url": f"{site_url}/pagos/webhook/",
        "external_reference": external_reference,
        "statement_descriptor": "PUNTO ASIS",
    }

    result = sdk.preference().create(preference_data)
    if result["status"] not in (200, 201):
        raise Exception(f"MP error {result['status']}: {result.get('response')}")
    return result["response"]
