"""
QR Forge Public REST API — v1
Auth: Bearer <api_key>
All responses: JSON  {'ok': True, ...} or {'error': '...', 'status': N}
"""
import json
import secrets
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .auth import api_key_required
from .models import APIKey, WebhookEndpoint
from qrapp.models import QRCode, DynamicLink
from qrapp.qr_utils import generate_qr_image
from qrapp.views import _build_content


# ── Docs page ─────────────────────────────────────────────────────────────────
@login_required(login_url='accounts:login')
def docs(request):
    keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'api/docs.html', {'keys': keys})


# ── Key management (session-auth — for the UI) ────────────────────────────────
@login_required(login_url='accounts:login')
@require_POST
@csrf_exempt
def create_key(request):
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    name = payload.get('name', '').strip()[:80] or 'My API Key'
    if APIKey.objects.filter(user=request.user).count() >= 10:
        return JsonResponse({'ok': False, 'error': 'Maximum 10 API keys per account'}, status=400)
    key = APIKey.objects.create(user=request.user, name=name)
    return JsonResponse({'ok': True, 'key': {
        'id': key.id, 'name': key.name, 'key': key.key,
        'created_at': key.created_at.strftime('%d %b %Y'),
    }})


@login_required(login_url='accounts:login')
@require_POST
@csrf_exempt
def revoke_key(request, pk):
    try:
        key = APIKey.objects.get(pk=pk, user=request.user)
        key.delete()
        return JsonResponse({'ok': True})
    except APIKey.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Key not found'}, status=404)


# ── Public API endpoints (Bearer auth) ────────────────────────────────────────
@csrf_exempt
@api_key_required
@require_POST
def api_generate(request):
    """
    POST /api/v1/generate/
    Body: { "type": "url", "url": "https://...", "qr_color": "#000000",
            "bg_color": "#ffffff", "style": "square", "size": 300 }
    Returns: { "ok": true, "image": "data:image/png;base64,...",
               "content": "...", "id": 42 }
    """
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    qr_type   = payload.get('type', 'url').lower()
    qr_color  = payload.get('qr_color', '#000000')
    bg_color  = payload.get('bg_color', '#ffffff')
    style     = payload.get('style', 'square')
    size      = max(100, min(1000, int(payload.get('size', 300))))
    label     = payload.get('label', '').strip()[:120]

    # build content string from payload
    content = _build_content(qr_type, payload, payload)
    if not content:
        return JsonResponse({'error': f'Missing required fields for type "{qr_type}"'}, status=400)

    image = generate_qr_image(content, size=size, color=qr_color, bg=bg_color, style=style)
    obj   = QRCode.objects.create(
        qr_type=qr_type, label=label, content=content,
        image_b64=image, qr_color=qr_color, bg_color=bg_color,
        qr_size=size, qr_style=style,
    )
    return JsonResponse({'ok': True, 'id': obj.id, 'content': content, 'image': image})


@csrf_exempt
@api_key_required
@require_GET
def api_list(request):
    """
    GET /api/v1/qrcodes/?page=1&type=url&q=search
    Returns paginated list of QR codes.
    """
    page    = max(1, int(request.GET.get('page', 1)))
    per     = min(50, int(request.GET.get('per_page', 20)))
    q       = request.GET.get('q', '').strip()
    qr_type = request.GET.get('type', '').strip()

    qs = QRCode.objects.all()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(label__icontains=q) | Q(content__icontains=q))
    if qr_type:
        qs = qs.filter(qr_type=qr_type)

    total = qs.count()
    pages = max(1, (total + per - 1) // per)
    qs    = qs[(page-1)*per: page*per]

    return JsonResponse({'ok': True, 'total': total, 'page': page, 'pages': pages,
        'items': [{
            'id':         q.id, 'type': q.qr_type, 'label': q.label,
            'content':    q.content[:100],
            'scan_count': q.scan_count,
            'created_at': q.created_at.isoformat(),
        } for q in qs]
    })


@csrf_exempt
@api_key_required
@require_GET
def api_get(request, pk):
    """GET /api/v1/qrcodes/<id>/ — full details including image."""
    try:
        obj = QRCode.objects.get(pk=pk)
    except QRCode.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'ok': True, 'item': {
        'id':         obj.id, 'type': obj.qr_type, 'label': obj.label,
        'content':    obj.content, 'image': obj.image_b64,
        'qr_color':   obj.qr_color, 'bg_color': obj.bg_color,
        'scan_count': obj.scan_count,
        'created_at': obj.created_at.isoformat(),
    }})


@csrf_exempt
@api_key_required
@require_POST
def api_delete(request, pk):
    """POST /api/v1/qrcodes/<id>/delete/"""
    try:
        QRCode.objects.get(pk=pk).delete()
        return JsonResponse({'ok': True})
    except QRCode.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ── Dynamic links via API ─────────────────────────────────────────────────────
@csrf_exempt
@api_key_required
@require_GET
def api_dynamic_list(request):
    """GET /api/v1/dynamic/"""
    links = DynamicLink.objects.all()
    return JsonResponse({'ok': True, 'links': [{
        'id':         l.id, 'short_code': l.short_code,
        'label':      l.label, 'target_url': l.target_url,
        'scan_count': l.scan_count, 'is_active': l.is_active,
        'created_at': l.created_at.isoformat(),
    } for l in links]})


@csrf_exempt
@api_key_required
@require_POST
def api_dynamic_create(request):
    """POST /api/v1/dynamic/  { "target_url": "...", "label": "..." }"""
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    target_url = payload.get('target_url', '').strip()
    if not target_url or not target_url.startswith(('http://', 'https://')):
        return JsonResponse({'error': 'A valid target_url is required'}, status=400)
    label = payload.get('label', '').strip()[:120]
    link  = DynamicLink.objects.create(target_url=target_url, label=label)
    base  = request.build_absolute_uri('/')
    redirect_url = f"{base}r/{link.short_code}/"
    img   = generate_qr_image(redirect_url, size=300)
    DynamicLink.objects.filter(pk=link.pk).update(image_b64=img)
    return JsonResponse({'ok': True, 'link': {
        'id':           link.id, 'short_code': link.short_code,
        'redirect_url': redirect_url, 'target_url': link.target_url,
    }})


@csrf_exempt
@api_key_required
@require_POST
def api_dynamic_update(request, pk):
    """POST /api/v1/dynamic/<id>/update/  { "target_url": "...", "is_active": true }"""
    try:
        link = DynamicLink.objects.get(pk=pk)
    except DynamicLink.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    if 'target_url' in payload:
        link.target_url = payload['target_url']
    if 'label' in payload:
        link.label = payload['label'][:120]
    if 'is_active' in payload:
        link.is_active = bool(payload['is_active'])
    link.save()
    return JsonResponse({'ok': True, 'target_url': link.target_url, 'is_active': link.is_active})


# ── Webhooks ──────────────────────────────────────────────────────────────────
@login_required(login_url='accounts:login')
@require_POST
@csrf_exempt
def create_webhook(request):
    try:
        p = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    url    = p.get('target_url', '').strip()
    event  = p.get('event', 'qr.scanned')
    if not url:
        return JsonResponse({'ok': False, 'error': 'target_url required'}, status=400)
    wh = WebhookEndpoint.objects.create(
        user=request.user, target_url=url,
        event=event, secret=secrets.token_hex(20),
    )
    return JsonResponse({'ok': True, 'webhook': {
        'id': wh.id, 'target_url': wh.target_url, 'event': wh.event, 'secret': wh.secret,
    }})


@login_required(login_url='accounts:login')
@require_POST
@csrf_exempt
def delete_webhook(request, pk):
    try:
        WebhookEndpoint.objects.get(pk=pk, user=request.user).delete()
        return JsonResponse({'ok': True})
    except WebhookEndpoint.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


# ── Account info ──────────────────────────────────────────────────────────────
@csrf_exempt
@api_key_required
@require_GET
def api_me(request):
    """GET /api/v1/me/ — returns info about the key owner."""
    u = request.api_user
    return JsonResponse({'ok': True, 'user': {
        'id':    u.id, 'email': u.email,
        'name':  f"{u.first_name} {u.last_name}".strip() or u.email,
        'qr_total':  QRCode.objects.count(),
        'dyn_total': DynamicLink.objects.count(),
    }})
