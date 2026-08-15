"""
Webhook dispatch service.
Fires signed HTTP POST requests to registered endpoints when events occur.
Runs in a background thread so it never blocks the QR redirect response.

SSRF hardening
--------------
target_url is entirely user-supplied, and this module makes a real
server-side HTTP request to it — the classic SSRF shape. Defense here is
"resolve, validate, then connect to the address we validated":

  1. Only https is accepted (validated again here, not just at creation —
     see create_webhook in views.py — because a target that was a valid
     public host when the webhook was created can change what it resolves
     to by the time it's actually delivered to).
  2. The hostname is resolved with getaddrinfo() and EVERY returned address
     is checked against the known private/loopback/link-local/reserved/
     multicast ranges (IPv4 and IPv6, including the 169.254.169.254-style
     cloud metadata range). If any candidate address is non-public, the
     whole destination is rejected — a rebinding attacker who only
     controls a fallback answer doesn't get a free pass.
  3. The actual TCP connection is opened directly to the ONE validated IP
     we picked, not by re-resolving the hostname at connect time. That's
     what actually closes the DNS-rebinding window (an attacker can't
     swap the DNS answer between "check" and "connect" if the address we
     connect to was already fixed).
  4. TLS is still validated against the original hostname (SNI +
     certificate hostname), which needs a small manual connection instead
     of the default urllib opener.
  5. Delivery uses http.client directly rather than urllib.request. Unlike
     urllib.request.urlopen, http.client never follows redirects on its
     own — a 3xx response is just returned to the caller. That's exactly
     the property we want: a webhook target must not be able to redirect
     us somewhere we didn't validate. A redirect response is logged and
     treated as a failed delivery, not followed.
"""
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import ssl
import threading
import http.client
from urllib.parse import urlsplit

from django.utils import timezone

logger = logging.getLogger('qrapp')

TIMEOUT_SECONDS = 4
MAX_RESPONSE_BYTES = 4096  # we only care about the status; bound the read regardless


class SSRFBlocked(Exception):
    pass


# Supplements Python's built-in is_private/is_reserved/etc checks, which
# vary slightly by Python version (e.g. the CGNAT range 100.64.0.0/10 isn't
# flagged as private on every version this project might run on). Checked
# in addition to, not instead of, the built-in properties below.
_EXTRA_BLOCKED_NETS = [ipaddress.ip_network(n) for n in [
    '100.64.0.0/10',    # CGNAT shared address space (RFC 6598)
    '192.0.0.0/24',     # IETF protocol assignments
    '192.88.99.0/24',   # 6to4 relay anycast
    '198.18.0.0/15',    # benchmarking
    '224.0.0.0/4',      # multicast (belt-and-suspenders w/ is_multicast)
    '::ffff:0:0/96',    # IPv4-mapped wrapper itself — real check happens
                         # after unwrapping below, this just ensures an
                         # unmapped/malformed one doesn't slip through
    '64:ff9b::/96',      # NAT64 well-known prefix (can embed a private v4 addr)
    '2001:db8::/32',    # documentation range
]]


def _is_public_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    # IPv4-mapped IPv6 addresses (::ffff:a.b.c.d) are flagged as "reserved"
    # by Python's ipaddress module at the IPv6-wrapper level regardless of
    # the embedded address, so they have to be unwrapped and re-checked as
    # their actual v4 address BEFORE applying the generic IPv6 checks below
    # — otherwise a legitimate public v4 address reached via its mapped v6
    # form would be wrongly rejected.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_public_ip(str(ip.ipv4_mapped))
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified):
        return False
    if any(ip in net for net in _EXTRA_BLOCKED_NETS):
        return False
    return True


def resolve_validated_ip(hostname: str) -> str:
    """
    Resolve hostname and return a single IP that's safe to connect to.
    Raises SSRFBlocked if resolution fails or ANY resolved address is
    non-public (fail closed on ambiguity, not just the first answer).
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFBlocked(f'Could not resolve host: {e}')

    ips = {info[4][0] for info in infos}
    if not ips:
        raise SSRFBlocked('No addresses resolved for host')

    for ip in ips:
        if not _is_public_ip(ip):
            raise SSRFBlocked(f'Destination resolves to a non-public address ({ip})')

    return next(iter(ips))


def validate_webhook_url(url: str) -> None:
    """
    Raises SSRFBlocked / ValueError with a human-readable message if `url`
    is not an acceptable webhook target. Used both at creation time (fast
    feedback) and immediately before every delivery (the real enforcement
    point, since DNS can change between the two).
    """
    parts = urlsplit(url)
    if parts.scheme != 'https':
        raise ValueError('Webhook target_url must use https')
    if not parts.hostname:
        raise ValueError('Webhook target_url must include a host')
    resolve_validated_ip(parts.hostname)  # raises SSRFBlocked if unsafe


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """An HTTPSConnection that connects to a pre-validated IP instead of
    re-resolving self.host, while still using self.host for the TLS SNI /
    certificate hostname check and the HTTP Host header."""

    def __init__(self, host, pinned_ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)
        context = self._context or ssl.create_default_context()
        self.sock = context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Same IP-pinning idea, for plain http. Real webhook targets are
    required to be https (validate_webhook_url enforces that at both
    creation and delivery time) — this exists only so the delivery
    transport itself is exercised by tests against a local plain-HTTP test
    server, without needing to stand up real TLS in the test suite."""

    def __init__(self, host, pinned_ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection((self._pinned_ip, self.port), self.timeout)


def _sign_payload(secret: str, body: bytes) -> str:
    """HMAC-SHA256 signature, hex-encoded — same scheme as Stripe/GitHub webhooks."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _deliver(url: str, secret: str, payload: dict):
    body = json.dumps(payload).encode()
    signature = _sign_payload(secret, body)

    try:
        validate_webhook_url(url)
        parts = urlsplit(url)
        ip = resolve_validated_ip(parts.hostname)
        port = parts.port or (443 if parts.scheme == 'https' else 80)
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
    except (SSRFBlocked, ValueError) as e:
        logger.warning('Webhook to %s blocked: %s', url, e)
        return

    conn_cls = _PinnedHTTPSConnection if parts.scheme == 'https' else _PinnedHTTPConnection
    conn = conn_cls(parts.hostname, ip, port, timeout=TIMEOUT_SECONDS)
    try:
        conn.request('POST', path, body=body, headers={
            'Content-Type': 'application/json',
            'Content-Length': str(len(body)),
            'X-QRForge-Signature': signature,
            'X-QRForge-Event': payload.get('event', ''),
            'User-Agent': 'QRForge-Webhooks/1.0',
        })
        resp = conn.getresponse()
        resp.read(MAX_RESPONSE_BYTES)  # bounded — we don't need the body, just don't leave it unread

        if 300 <= resp.status < 400:
            # Deliberately not following redirects — see module docstring.
            logger.warning('Webhook to %s returned a redirect (HTTP %s) — not following it', url, resp.status)
        elif 200 <= resp.status < 300:
            logger.info('Webhook delivered to %s: HTTP %s', url, resp.status)
        else:
            logger.warning('Webhook to %s rejected: HTTP %s', url, resp.status)
    except Exception as e:
        logger.warning('Webhook to %s failed: %s', url, e)
    finally:
        conn.close()


def fire_event(event: str, data: dict):
    """
    Dispatch `event` to all active WebhookEndpoints subscribed to it.
    Non-blocking: each delivery runs in its own daemon thread, and each
    delivery has its own bounded socket timeout (TIMEOUT_SECONDS), so a
    slow or malicious target can delay at most that one thread — it can't
    hang request handling or accumulate unbounded resources.
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
