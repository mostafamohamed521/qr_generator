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
    if not items or len(items) > 50:
        return JsonResponse({'ok': False, 'error': 'Send 1–50 items'})

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
