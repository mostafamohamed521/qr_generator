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
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta

from .models import QRCode
from .forms import (URLForm, TextForm, ContactForm, WiFiForm,
                    SMSForm, EmailForm, PhoneForm, LocationForm)
from .qr_utils import (generate_qr_image, generate_qr_svg,
                       build_url, build_vcard, build_wifi,
                       build_sms, build_email, build_phone, build_location)


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
    if qr_type == 'url':
        return build_url(d['url'])
    elif qr_type == 'text':
        return d['text']
    elif qr_type == 'contact':
        return build_vcard(d)
    elif qr_type == 'wifi':
        return build_wifi(d['ssid'], d.get('password', ''), d['encryption'])
    elif qr_type == 'sms':
        return build_sms(d['phone'], d['message'])
    elif qr_type == 'email':
        return build_email(d['email'], d.get('subject', ''), d.get('body', ''))
    elif qr_type == 'phone':
        return build_phone(d['phone'])
    elif qr_type == 'location':
        return build_location(d['latitude'], d['longitude'])
    return ''


# ── pages ─────────────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'index.html')


def analytics(request):
    return render(request, 'analytics.html')


def dynamic(request):
    return render(request, 'dynamic.html')


def bulk(request):
    return render(request, 'bulk.html')


def scanner(request):
    return render(request, 'scanner.html')


# ── API ───────────────────────────────────────────────────────────────────────

@require_POST
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

    image = generate_qr_image(content, size=size, color=color, bg=bg, style=style, logo_b64=logo)

    QRCode.objects.create(
        qr_type=qr_type, label=label, content=content,
        qr_color=color, bg_color=bg, qr_size=size,
        qr_style=style, image_b64=image,
    )

    return JsonResponse({'ok': True, 'image': image, 'content': content})


@require_GET
def history(request):
    qs = QRCode.objects.all()

    q_str = request.GET.get('q', '').strip()
    if q_str:
        from django.db.models import Q
        qs = qs.filter(Q(label__icontains=q_str) | Q(content__icontains=q_str))

    qr_type = request.GET.get('type', '').strip()
    if qr_type and qr_type != 'all':
        qs = qs.filter(qr_type=qr_type)

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
    } for q in qs]
    return JsonResponse({'ok': True, 'items': items, 'total': total, 'page': page, 'pages': pages})


@require_POST
def delete(request, pk):
    try:
        QRCode.objects.get(pk=pk).delete()
        return JsonResponse({'ok': True})
    except QRCode.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@require_POST
def clear(request):
    QRCode.objects.all().delete()
    return JsonResponse({'ok': True})


@require_GET
def analytics_data(request):
    total = QRCode.objects.count()
    
    # Type breakdown
    by_type = list(
        QRCode.objects.values('qr_type')
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
        QRCode.objects.filter(created_at__gte=seven_days_ago)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    for item in by_day:
        item['day'] = item['day'].strftime('%d %b')

    # Style breakdown
    by_style = list(
        QRCode.objects.values('qr_style')
        .annotate(count=Count('id'))
    )

    # Most used colors
    recent = list(
        QRCode.objects.order_by('-created_at')[:5]
        .values('qr_color', 'bg_color', 'label', 'qr_type', 'created_at', 'image_b64')
    )
    for r in recent:
        r['created_at'] = r['created_at'].strftime('%d %b %Y')

    from django.db.models import Sum
    total_scans = QRCode.objects.aggregate(s=Sum('scan_count'))['s'] or 0

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

    results = []
    for item in items:
        text = str(item.get('content', '')).strip()
        label = str(item.get('label', '')).strip()
        if not text:
            continue
        try:
            image = generate_qr_image(text, size=size, color=color, bg=bg, style=style)
            obj = QRCode.objects.create(
                qr_type='text', label=label, content=text,
                qr_color=color, bg_color=bg, qr_size=size,
                qr_style=style, image_b64=image,
            )
            results.append({'id': obj.id, 'label': label or text[:30], 'image': image})
        except Exception as e:
            results.append({'id': None, 'label': label or text[:30], 'error': str(e)})

    return JsonResponse({'ok': True, 'results': results})


@require_GET
def export_svg(request, pk):
    try:
        q = QRCode.objects.get(pk=pk)
    except QRCode.DoesNotExist:
        return HttpResponse('Not found', status=404)

    svg_data = generate_qr_svg(q.content, color=q.qr_color, bg=q.bg_color)
    filename = (q.label or f'qr-{pk}').replace(' ', '_')
    response = HttpResponse(svg_data, content_type='image/svg+xml')
    response['Content-Disposition'] = f'attachment; filename="{filename}.svg"'
    return response


# ── Sprint 3: CSV export ───────────────────────────────────────────────────────
import csv
from django.http import HttpResponse

@require_GET
def export_csv(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="qr_history.csv"'
    response.write('\ufeff')  # BOM for Excel compatibility

    writer = csv.writer(response)
    writer.writerow(['ID', 'Type', 'Label', 'Content', 'Color', 'Background', 'Size', 'Style', 'Scan Count', 'Created At'])

    qs = QRCode.objects.all()

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

    from django.shortcuts import redirect as dj_redirect
    return dj_redirect(link.target_url, permanent=False)


@require_GET
def dynamic_list(request):
    """Return all dynamic links as JSON for the dashboard."""
    links = DynamicLink.objects.all()
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
def dynamic_create(request):
    """Create a new dynamic QR link."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    target_url = payload.get('target_url', '').strip()
    if not target_url or not target_url.startswith(('http://', 'https://')):
        return JsonResponse({'ok': False, 'error': 'A valid URL is required'}, status=400)

    label     = payload.get('label', '').strip()[:120]
    qr_color  = payload.get('qr_color', '#000000')
    bg_color  = payload.get('bg_color', '#ffffff')
    qr_style  = payload.get('qr_style', 'square')

    link      = DynamicLink.objects.create(
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
def dynamic_update(request, pk):
    """Update the target URL and/or label of a dynamic link."""
    try:
        link = DynamicLink.objects.get(pk=pk)
    except DynamicLink.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    target_url = payload.get('target_url', '').strip()
    if target_url:
        if not target_url.startswith(('http://', 'https://')):
            return JsonResponse({'ok': False, 'error': 'A valid URL is required'}, status=400)
        link.target_url = target_url

    if 'label' in payload:
        link.label = payload['label'][:120]
    if 'is_active' in payload:
        link.is_active = bool(payload['is_active'])
    link.save()

    return JsonResponse({'ok': True, 'target_url': link.target_url, 'label': link.label, 'is_active': link.is_active})


@require_POST
def dynamic_delete(request, pk):
    """Delete a dynamic link and all its scan events."""
    try:
        DynamicLink.objects.get(pk=pk).delete()
        return JsonResponse({'ok': True})
    except DynamicLink.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)


@require_GET
def dynamic_stats(request, pk):
    """Per-link scan stats: total, by day (last 14 days)."""
    try:
        link = DynamicLink.objects.get(pk=pk)
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
def save_scan(request):
    """Save a scanner result to QR history."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    content = payload.get('content', '').strip()
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

    img = generate_qr_image(content, size=200)
    obj = QRCode.objects.create(
        qr_type=qr_type, label=f'Scanned: {content[:40]}',
        content=content, image_b64=img,
    )
    return JsonResponse({'ok': True, 'id': obj.id, 'type': qr_type})
