"""
Simple in-memory rate limiter.
Tracks request counts per IP per minute for sensitive endpoints.
For production, replace with Redis-backed django-ratelimit.
"""
import time
import logging
from collections import defaultdict
from threading import Lock

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger('qrapp')

_store  = defaultdict(list)   # ip -> [timestamps]
_lock   = Lock()

# Endpoint patterns and their limits (requests per 60 s)
_LIMITS = {
    '/api/generate/':       getattr(settings, 'RATE_LIMIT_GENERATE', 30),
    '/api/bulk/':           getattr(settings, 'RATE_LIMIT_GENERATE', 30),
    '/api/v1/generate/':    getattr(settings, 'RATE_LIMIT_GENERATE', 30),
    '/accounts/login/':     getattr(settings, 'RATE_LIMIT_AUTH', 10),
    '/accounts/register/':  getattr(settings, 'RATE_LIMIT_AUTH', 10),
    '/accounts/2fa/verify/': getattr(settings, 'RATE_LIMIT_AUTH', 10),
    '/accounts/forgot-password/': getattr(settings, 'RATE_LIMIT_AUTH', 10),
    '/accounts/resend-verification/': getattr(settings, 'RATE_LIMIT_AUTH', 10),
    '/contact/submit/': getattr(settings, 'RATE_LIMIT_AUTH', 10),
}
_GLOBAL_LIMIT = getattr(settings, 'RATE_LIMIT_GLOBAL', 200)
_WINDOW       = 60   # seconds


def _get_ip(request):
    # X-Forwarded-For is attacker-controlled unless a reverse proxy in front
    # of us overwrites/strips it. Only trust it when TRUST_PROXY_HEADERS is
    # explicitly on (see settings.py) — otherwise a client could send a
    # fresh fake value on every request and bypass rate limiting entirely.
    if getattr(settings, 'TRUST_PROXY_HEADERS', False):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()[:45]
    return request.META.get('REMOTE_ADDR', '0.0.0.0')[:45]


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ('POST', 'GET'):
            ip    = _get_ip(request)
            now   = time.monotonic()
            key   = ip

            # Per-endpoint limit. Matched by substring (not startswith/prefix)
            # so this still applies under the i18n URL prefix (e.g.
            # /ar/accounts/login/), which a startswith check would miss.
            for pattern, limit in _LIMITS.items():
                if pattern in request.path:
                    ekey = f'{ip}:{pattern}'
                    if self._is_limited(ekey, now, limit):
                        logger.warning('Rate limit hit: %s %s', ip, request.path)
                        return JsonResponse(
                            {'ok': False, 'error': 'Rate limit exceeded — try again in a minute.'},
                            status=429,
                        )

            # global API limit — covers this app's own session-based API
            # surface (/app/api/...) and the public REST API (/api/v1/...).
            # The public API previously had no rate limit at all here (only
            # the specific /api/v1/generate/ entry above did), so a caller
            # with a valid key — or none, since auth still runs after this
            # middleware — could hammer /api/v1/qrcodes/, /me/, etc. freely.
            if '/app/api' in request.path or '/api/v1/' in request.path:
                if self._is_limited(key, now, _GLOBAL_LIMIT):
                    return JsonResponse(
                        {'ok': False, 'error': 'Too many requests.'},
                        status=429,
                    )

        return self.get_response(request)

    @staticmethod
    def _is_limited(key, now, limit):
        with _lock:
            hits  = _store[key]
            # drop old entries
            cutoff = now - _WINDOW
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= limit:
                return True
            hits.append(now)
            return False
