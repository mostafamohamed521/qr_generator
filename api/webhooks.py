"""
Webhook dispatch service.
Fires signed HTTP POST requests to registered endpoints when events occur.
Runs in a background thread so it never blocks the QR redirect response.
"""
import hashlib
import hmac
import json
import logging
import threading
import urllib.request
import urllib.error

from django.utils import timezone

logger = logging.getLogger('qrapp')

TIMEOUT_SECONDS = 4


def _sign_payload(secret: str, body: bytes) -> str:
    """HMAC-SHA256 signature, hex-encoded — same scheme as Stripe/GitHub webhooks."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _deliver(url: str, secret: str, payload: dict):
    body = json.dumps(payload).encode()
    signature = _sign_payload(secret, body)

    req = urllib.request.Request(
        url, data=body, method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-QRForge-Signature': signature,
            'X-QRForge-Event': payload.get('event', ''),
            'User-Agent': 'QRForge-Webhooks/1.0',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            logger.info('Webhook delivered to %s: HTTP %s', url, resp.status)
    except urllib.error.HTTPError as e:
        logger.warning('Webhook to %s rejected: HTTP %s', url, e.code)
    except Exception as e:
        logger.warning('Webhook to %s failed: %s', url, e)


def fire_event(event: str, data: dict):
    """
    Dispatch `event` to all active WebhookEndpoints subscribed to it.
    Non-blocking: each delivery runs in its own daemon thread.
    """
    from .models import WebhookEndpoint  # local import avoids circular import at app load

    endpoints = WebhookEndpoint.objects.filter(event=event, is_active=True)
    if not endpoints.exists():
        return

    payload = {
        'event': event,
        'timestamp': timezone.now().isoformat(),
        **data,
    }

    for ep in endpoints:
        secret = ep.secret or ''
        t = threading.Thread(
            target=_deliver, args=(ep.target_url, secret, payload), daemon=True
        )
        t.start()
