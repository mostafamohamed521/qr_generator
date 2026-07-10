"""
API key authentication helpers.
Usage: decorate views with @api_key_required
"""
import hashlib
from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from .models import APIKey


def get_api_key(request):
    """Extract API key from Authorization header or ?api_key= param."""
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return request.GET.get('api_key', '').strip()


def authenticate_api_key(request):
    """Return (user, api_key_obj) or (None, None)."""
    raw = get_api_key(request)
    if not raw:
        return None, None
    try:
        key_obj = APIKey.objects.select_related('user').get(key=raw, is_active=True)
        # update last_used_at (non-blocking)
        APIKey.objects.filter(pk=key_obj.pk).update(last_used_at=timezone.now())
        return key_obj.user, key_obj
    except APIKey.DoesNotExist:
        return None, None


def api_key_required(view_fn):
    """Decorator: require valid API key, set request.api_user and request.api_key."""
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        user, key_obj = authenticate_api_key(request)
        if user is None:
            return JsonResponse({
                'error': 'Authentication required. Pass your API key as Authorization: Bearer <key>',
                'docs':  '/api/v1/docs/',
            }, status=401)
        request.api_user = user
        request.api_key  = key_obj
        return view_fn(request, *args, **kwargs)
    return wrapper
