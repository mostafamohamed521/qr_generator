"""
views.py
--------
index        GET  /
generate     POST /api/generate/
history      GET  /api/history/
delete       POST /api/delete/<id>/
clear        POST /api/clear/
analytics    GET  /analytics/
bulk         GET  /bulk/
bulk_gen     POST /api/bulk/
scanner      GET  /scanner/
export_svg   GET  /api/export-svg/<id>/
"""
import json
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta

from .models import QRCode


def json_login_required(view_fn):
    """
    Like @login_required, but for JSON/AJAX endpoints: an unauthenticated
    request gets a 401 JSON body instead of a 302 redirect to the login page
    (a redirect would otherwise land in the caller's .json() as a parse error).
    """
    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'ok': False, 'error': 'Authentication required'}, status=401)
        return view_fn(request, *args, **kwargs)
    return wrapper
from .forms import (URLForm, TextForm, ContactForm, WiFiForm,
                    SMSForm, EmailForm, PhoneForm, LocationForm)
from .qr_utils import (generate_qr_image, generate_qr_svg, QRContentTooLong,
                       build_url, build_vcard, build_wifi,
                       build_sms, build_email, build_phone, build_location)
import re


def _safe_filename(name, fallback):
    """Strip anything that isn't safe in a Content-Disposition filename
    (quotes, control/newline characters) so a crafted label can't break
    the response header."""
    name = re.sub(r'[\r\n"\\\x00-\x1f]', '', name or '').strip()
    return name.replace(' ', '_') or fallback


# ── helpers ───────────────────────────────────────────────────────────────────

FORM_MAP = {
    'url':      URLForm,
    'text':     TextForm,
    'contact':  ContactForm,
    'wifi':     WiFiForm,
    'sms':      SMSForm,
    'email':    EmailForm,
    'phone':    PhoneForm,
    'location': LocationForm,
}


def _parse_size(raw):
    try:
        return max(100, min(1000, int(raw)))
    except (TypeError, ValueError):
        return 300


def _build_content(qr_type, d, request_post):
    """
    Build the encoded string for a QR code from a dict of fields.
    Uses .get() everywhere so missing/malformed input (e.g. from the public
    API, which skips Django form validation) returns empty content instead
    of raising KeyError — callers treat empty content as a validation error.
    """
    if qr_type == 'url':
        url = d.get('url', '').strip()
        return build_url(url) if url else ''
    elif qr_type == 'text':
        return d.get('text', '').strip()
    elif qr_type == 'contact':
        return build_vcard(d) if (d.get('first_name') or d.get('last_name')) else ''
    elif qr_type == 'wifi':
        ssid = d.get('ssid', '').strip()
        return build_wifi(ssid, d.get('password', ''), d.get('encryption', 'WPA')) if ssid else ''
    elif qr_type == 'sms':
        phone = d.get('phone', '').strip()
        return build_sms(phone, d.get('message', '')) if phone else ''
    elif qr_type == 'email':
        email = d.get('email', '').strip()
        return build_email(email, d.get('subject', ''), d.get('body', '')) if email else ''
    elif qr_type == 'phone':
        phone = d.get('phone', '').strip()
        return build_phone(phone) if phone else ''
    elif qr_type == 'location':
        lat, lng = d.get('latitude', ''), d.get('longitude', '')
        lat, lng = str(lat).strip(), str(lng).strip()
        return build_location(lat, lng) if (lat and lng) else ''
    return ''


# ── pages ─────────────────────────────────────────────────────────────────────
# These are the app's dashboard pages — LOGIN_REDIRECT_URL points here, so they
# were always meant to sit behind auth. @login_required redirects to the login
# page (correct for a full page load, unlike the JSON endpoints below).

@login_required(login_url='accounts:login')
def index(request):
    return render(request, 'index.html')


@login_required(login_url='accounts:login')
def analytics(request):
    return render(request, 'analytics.html')


@login_required(login_url='accounts:login')
def dynamic(request):
    return render(request, 'dynamic.html')


@login_required(login_url='accounts:login')
def bulk(request):
    return render(request, 'bulk.html')


@login_required(login_url='accounts:login')
def scanner(request):
    return render(request, 'scanner.html')


# ── API ───────────────────────────────────────────────────────────────────────

@require_POST
@json_login_required
def generate(request):
    qr_type = request.POST.get('type', 'url')
    color   = request.POST.get('qr_color', '#000000').strip() or '#000000'
    bg      = request.POST.get('bg_color', '#ffffff').strip() or '#ffffff'
    style   = request.POST.get('style', 'square')
    label   = request.POST.get('label', '').strip()
    size    = _parse_size(request.POST.get('size', 300))
    logo    = request.POST.get('logo_b64', '').strip() or None

    FormClass = FORM_MAP.get(qr_type)
    if not FormClass:
        return JsonResponse({'ok': False, 'error': f'Unknown type: {qr_type}'})

    form = FormClass(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': form.errors.as_text()})

    content = _build_content(qr_type, form.cleaned_data, request.POST)
    if not content:
        return JsonResponse({'ok': False, 'error': 'No content to encode'})

    from billing.views import reserve_qr_quota
    with transaction.atomic():
        allowed, remaining = reserve_qr_quota(request.user, requested=1)
        if not allowed:
            return JsonResponse({
                'ok': False, 'code': 'quota_exceeded',
                'error': "You've reached your monthly QR code limit. Upgrade to Pro for unlimited codes.",
                'remaining': max(remaining, 0),
            }, status=429)

        try:
            image = generate_qr_image(content, size=size, color=color, bg=bg, style=style, logo_b64=logo)
        except QRContentTooLong as e:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)

        QRCode.objects.create(
            user=request.user,
            qr_type=qr_type, label=label, content=content,
            qr_color=color, bg_color=bg, qr_size=size,
            qr_style=style, image_b64=image,
        )

    return JsonResponse({'ok': True, 'image': image, 'content': content})


@require_GET
@json_login_required
def history(request):
    qs = QRCode.objects.filter(user=request.user)

    q_str = request.GET.get('q', '').strip()
    if q_str:
        from django.db.models import Q
        qs = qs.filter(Q(label__icontains=q_str) | Q(content__icontains=q_str))

    qr_type = request.GET.get('type', '').strip()
    if qr_type and qr_type != 'all':
        qs = qs.filter(qr_type=qr_type)

    if request.GET.get('favorites') == '1':
        qs = qs.filter(is_favorite=True)

    page     = max(1, int(request.GET.get('page', 1)))
    per_page = 12
    total    = qs.count()
    pages    = max(1, (total + per_page - 1) // per_page)
    qs       = qs[(page - 1) * per_page: page * per_page]

    items = [{
        'id':         q.id,
        'qr_type':    q.qr_type,
        'type_label': q.get_qr_type_display(),
        'label':      q.display_label(),
        'created_at': q.created_at.strftime('%d %b %Y, %H:%M'),
        'image':      q.image_b64,
        'qr_color':   q.qr_color,
        'bg_color':   q.bg_color,
        'content':    q.content,
        'scan_count': q.scan_count,
        'is_favorite': q.is_favorite,
    } for q in qs]
    return JsonResponse({'ok': True, 'items': items, 'total': total, 'page': page, 'pages': pages})


@require_POST
@json_login_required
def toggle_favorite(request, pk):
    try:
        q = QRCode.objects.get(pk=pk, user=request.user)
    except QRCode.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)
    q.is_favorite = not q.is_favorite
    q.save(update_fields=['is_favorite'])
    return JsonResponse({'ok': True, 'is_favorite': q.is_favorite})


@require_POST
@json_login_required
def duplicate(request, pk):
    try:
        src = QRCode.objects.get(pk=pk, user=request.user)
    except QRCode.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)

    from billing.views import reserve_qr_quota
    with transaction.atomic():
        allowed, remaining = reserve_qr_quota(request.user, requested=1)
        if not allowed:
            return JsonResponse({
                'ok': False, 'code': 'quota_exceeded',
                'error': "You've reached your monthly QR code limit. Upgrade to Pro for unlimited codes.",
                'remaining': max(remaining, 0),
            }, status=429)

        copy = QRCode.objects.create(
            user=request.user,
            qr_type=src.qr_type,
            label=(src.label + ' (copy)')[:120] if src.label else '',
            content=src.content,
            qr_color=src.qr_color,
            bg_color=src.bg_color,
            qr_size=src.qr_size,
            qr_style=src.qr_style,
            image_b64=src.image_b64,
        )
    return JsonResponse({'ok': True, 'id': copy.id, 'image': copy.image_b64, 'label': copy.display_label()})


@require_POST
@json_login_required
def delete(request, pk):
    try:
        QRCode.objects.get(pk=pk, user=request.user).delete()
        return JsonResponse({'ok': True})
    except QRCode.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@require_POST
@json_login_required
def clear(request):
    QRCode.objects.filter(user=request.user).delete()
    return JsonResponse({'ok': True})


@require_GET
@json_login_required
def analytics_data(request):
    base_qs = QRCode.objects.filter(user=request.user)
    total = base_qs.count()

    # Type breakdown
    by_type = list(
        base_qs.values('qr_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    for item in by_type:
        for choice_val, choice_label in QRCode.TYPE_CHOICES:
            if item['qr_type'] == choice_val:
                item['label'] = choice_label
                break

    # Last 7 days activity
    seven_days_ago = timezone.now() - timedelta(days=7)
    by_day = list(
        base_qs.filter(created_at__gte=seven_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    for item in by_day:
        item['day'] = item['day'].strftime('%d %b')

    # Style breakdown
    by_style = list(
        base_qs.values('qr_style')
        .annotate(count=Count('id'))
    )

    # Most used colors
    recent = list(
        base_qs.order_by('-created_at')[:5]
        .values('qr_color', 'bg_color', 'label', 'qr_type', 'created_at', 'image_b64')
    )
    for r in recent:
        r['created_at'] = r['created_at'].strftime('%d %b %Y')

    from django.db.models import Sum
    total_scans = base_qs.aggregate(s=Sum('scan_count'))['s'] or 0

    return JsonResponse({
        'ok': True,
        'total': total,
        'total_scans': total_scans,
        'by_type': by_type,
        'by_day': by_day,
        'by_style': by_style,
        'recent': recent,
    })


@require_POST
@json_login_required
def bulk_generate(request):
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'})

    items = payload.get('items', [])
    if not items or len(items) > 200:
        return JsonResponse({'ok': False, 'error': 'Send 1–200 items'})

    color  = payload.get('qr_color', '#000000')
    bg     = payload.get('bg_color', '#ffffff')
    style  = payload.get('style', 'square')
    size   = _parse_size(payload.get('size', 300))

    # Pre-filter to the items that will actually attempt a QRCode row, so the
    # quota check matches what's really about to be created.
    valid_items = []
    for item in items:
        text = str(item.get('content', '')).strip()
        if text:
            valid_items.append((text, str(item.get('label', '')).strip()))

    results = []
    from billing.views import reserve_qr_quota
    with transaction.atomic():
        allowed, remaining = reserve_qr_quota(request.user, requested=len(valid_items))
        if not allowed:
            return JsonResponse({
                'ok': False, 'code': 'quota_exceeded',
                'error': f"This batch of {len(valid_items)} would exceed your monthly QR code limit "
                         f"({max(remaining, 0)} remaining). Reduce the batch size or upgrade to Pro.",
                'remaining': max(remaining, 0),
            }, status=429)

        for text, label in valid_items:
            try:
                image = generate_qr_image(text, size=size, color=color, bg=bg, style=style)
                # Nested atomic (savepoint): if this single item's create()
                # raises a DB error, only its savepoint rolls back — it
                # doesn't poison the outer transaction (and thus the rest of
                # the batch, or the quota reservation) the way an uncaught
                # DB exception inside a single atomic() block would on
                # backends like PostgreSQL.
                with transaction.atomic():
                    obj = QRCode.objects.create(
                        user=request.user,
                        qr_type='text', label=label, content=text,
                        qr_color=color, bg_color=bg, qr_size=size,
                        qr_style=style, image_b64=image,
                    )
                results.append({'id': obj.id, 'label': label or text[:30], 'image': image})
            except Exception as e:
                results.append({'id': None, 'label': label or text[:30], 'error': str(e)})

    return JsonResponse({'ok': True, 'results': results})


@require_GET
@login_required(login_url='accounts:login')
def export_svg(request, pk):
    try:
        q = QRCode.objects.get(pk=pk, user=request.user)
    except QRCode.DoesNotExist:
        return HttpResponse('Not found', status=404)

    try:
        svg_data = generate_qr_svg(q.content, color=q.qr_color, bg=q.bg_color)
    except QRContentTooLong:
        return HttpResponse('Content too long to export', status=400)
    filename = _safe_filename(q.label, f'qr-{pk}')
    response = HttpResponse(svg_data, content_type='image/svg+xml')
    response['Content-Disposition'] = f'attachment; filename="{filename}.svg"'
    return response


# ── Sprint 3: CSV export ───────────────────────────────────────────────────────
import csv
from django.http import HttpResponse

@require_GET
@login_required(login_url='accounts:login')
def export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="qr_history.csv"'
    response.write('\ufeff')  # BOM for Excel compatibility

    writer = csv.writer(response)
    writer.writerow(['ID', 'Type', 'Label', 'Content', 'Color', 'Background', 'Size', 'Style', 'Scan Count', 'Created At'])

    qs = QRCode.objects.filter(user=request.user)

    q_str = request.GET.get('q', '').strip()
    if q_str:
        from django.db.models import Q
        qs = qs.filter(Q(label__icontains=q_str) | Q(content__icontains=q_str))

    qr_type = request.GET.get('type', '').strip()
    if qr_type and qr_type != 'all':
        qs = qs.filter(qr_type=qr_type)

    for q in qs:
        writer.writerow([
            q.id,
            q.get_qr_type_display(),
            q.label,
            q.content,
            q.qr_color,
            q.bg_color,
            q.qr_size,
            q.qr_style,
            q.scan_count,
            q.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


# ── Sprint 4: Dynamic QR ──────────────────────────────────────────────────────
import hashlib
from django.views.decorators.http import require_http_methods
from .models import DynamicLink, ScanEvent
from .qr_utils import generate_qr_image


def dynamic_redirect(request, short_code):
    """Public redirect endpoint — scanned by a phone camera."""
    try:
        link = DynamicLink.objects.get(short_code=short_code, is_active=True)
    except DynamicLink.DoesNotExist:
        from django.http import Http404
        raise Http404

    # record scan
    ip  = request.META.get('REMOTE_ADDR', '')
    ScanEvent.objects.create(
        link=link,
        ip_hash=hashlib.sha256(ip.encode()).hexdigest()[:16],
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        referer=request.META.get('HTTP_REFERER', '')[:500],
    )
    from django.db.models import F
    DynamicLink.objects.filter(pk=link.pk).update(scan_count=F('scan_count') + 1)

    # Fire webhook (non-blocking — runs in a background thread)
    from api.webhooks import fire_event
    fire_event('qr.scanned', {
        'short_code': link.short_code,
        'target_url': link.target_url,
        'label':      link.label,
        'scanned_at': timezone.now().isoformat(),
    })

    from django.shortcuts import redirect as dj_redirect
    return dj_redirect(link.target_url, permanent=False)


@require_GET
@json_login_required
def dynamic_list(request):
    """Return the caller's dynamic links as JSON for the dashboard."""
    links = DynamicLink.objects.filter(user=request.user)
    return JsonResponse({'ok': True, 'links': [{
        'id':         l.id,
        'short_code': l.short_code,
        'label':      l.display_label(),
        'target_url': l.target_url,
        'scan_count': l.scan_count,
        'is_active':  l.is_active,
        'created_at': l.created_at.strftime('%d %b %Y'),
        'image':      l.image_b64,
    } for l in links]})


@require_POST
@json_login_required
def dynamic_create(request):
    """Create a new dynamic QR link."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    target_url = payload.get('target_url', '').strip()
    if not target_url or not target_url.startswith(('http://', 'https://')) or len(target_url) > 2000:
        return JsonResponse({'ok': False, 'error': 'A valid URL is required'}, status=400)

    label     = payload.get('label', '').strip()[:120]
    qr_color  = payload.get('qr_color', '#000000')
    bg_color  = payload.get('bg_color', '#ffffff')
    qr_style  = payload.get('qr_style', 'square')

    link      = DynamicLink.objects.create(
        user=request.user,
        target_url=target_url, label=label,
        qr_color=qr_color, bg_color=bg_color, qr_style=qr_style,
    )

    # build the redirect URL that goes in the QR code
    base = request.build_absolute_uri('/')[:-1]
    redirect_url = f'{base}/r/{link.short_code}/'
    img  = generate_qr_image(redirect_url, size=300, color=qr_color, bg=bg_color, style=qr_style)
    DynamicLink.objects.filter(pk=link.pk).update(image_b64=img)
    link.refresh_from_db()

    return JsonResponse({'ok': True, 'link': {
        'id':           link.id,
        'short_code':   link.short_code,
        'redirect_url': redirect_url,
        'image':        link.image_b64,
        'target_url':   link.target_url,
        'label':        link.display_label(),
        'scan_count':   link.scan_count,
    }})


@require_POST
@json_login_required
def dynamic_update(request, pk):
    """Update the target URL and/or label of a dynamic link."""
    try:
        link = DynamicLink.objects.get(pk=pk, user=request.user)
    except DynamicLink.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    target_url = payload.get('target_url', '').strip()
    if target_url:
        if not target_url.startswith(('http://', 'https://')) or len(target_url) > 2000:
            return JsonResponse({'ok': False, 'error': 'A valid URL is required'}, status=400)
        link.target_url = target_url

    if 'label' in payload:
        link.label = payload['label'][:120]
    if 'is_active' in payload:
        link.is_active = bool(payload['is_active'])
    link.save()

    return JsonResponse({'ok': True, 'target_url': link.target_url, 'label': link.label, 'is_active': link.is_active})


@require_POST
@json_login_required
def dynamic_delete(request, pk):
    """Delete a dynamic link and all its scan events."""
    try:
        DynamicLink.objects.get(pk=pk, user=request.user).delete()
        return JsonResponse({'ok': True})
    except DynamicLink.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@require_GET
@json_login_required
def dynamic_stats(request, pk):
    """Per-link scan stats: total, by day (last 14 days)."""
    try:
        link = DynamicLink.objects.get(pk=pk, user=request.user)
    except DynamicLink.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)

    fourteen_days_ago = timezone.now() - timedelta(days=14)
    by_day = list(
        ScanEvent.objects.filter(link=link, scanned_at__gte=fourteen_days_ago)
        .annotate(day=TruncDate('scanned_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    for item in by_day:
        item['day'] = item['day'].strftime('%d %b')

    return JsonResponse({
        'ok':         True,
        'total':      link.scan_count,
        'by_day':     by_day,
        'target_url': link.target_url,
        'label':      link.display_label(),
        'is_active':  link.is_active,
        'created_at': link.created_at.strftime('%d %b %Y'),
    })


@require_POST
@json_login_required
def save_scan(request):
    """Save a scanner result to QR history."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    content = payload.get('content', '').strip()[:2000]
    if not content:
        return JsonResponse({'ok': False, 'error': 'No content'}, status=400)

    # detect type
    if content.startswith(('http://', 'https://')):
        qr_type = 'url'
    elif content.startswith('WIFI:'):
        qr_type = 'wifi'
    elif content.startswith('BEGIN:VCARD'):
        qr_type = 'contact'
    elif content.startswith('mailto:'):
        qr_type = 'email'
    elif content.startswith('sms:') or content.startswith('SMSTO:'):
        qr_type = 'sms'
    elif content.startswith('tel:'):
        qr_type = 'phone'
    elif content.startswith('geo:'):
        qr_type = 'location'
    else:
        qr_type = 'text'

    try:
        img = generate_qr_image(content, size=200)
    except QRContentTooLong as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    obj = QRCode.objects.create(
        user=request.user,
        qr_type=qr_type, label=f'Scanned: {content[:40]}',
        content=content, image_b64=img,
    )
    return JsonResponse({'ok': True, 'id': obj.id, 'type': qr_type})
