"""
views.py
--------
index      GET  /
generate   POST /api/generate/
history    GET  /api/history/
delete     POST /api/delete/<id>/
clear      POST /api/clear/
"""
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

from .models import QRCode
from .forms import (URLForm, TextForm, ContactForm, WiFiForm,
                    SMSForm, EmailForm, PhoneForm, LocationForm)
from .qr_utils import (generate_qr_image,
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


# ── views ─────────────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'index.html')


@require_POST
def generate(request):
    qr_type  = request.POST.get('type', 'url')
    color    = request.POST.get('qr_color', '#000000').strip() or '#000000'
    bg       = request.POST.get('bg_color', '#ffffff').strip() or '#ffffff'
    style    = request.POST.get('style', 'square')
    label    = request.POST.get('label', '').strip()
    size     = _parse_size(request.POST.get('size', 300))

    FormClass = FORM_MAP.get(qr_type)
    if not FormClass:
        return JsonResponse({'ok': False, 'error': f'Unknown type: {qr_type}'})

    form = FormClass(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'error': form.errors.as_text()})

    d = form.cleaned_data
    content = ''

    if qr_type == 'url':
        content = build_url(d['url'])
    elif qr_type == 'text':
        content = d['text']
    elif qr_type == 'contact':
        content = build_vcard(d)
    elif qr_type == 'wifi':
        content = build_wifi(d['ssid'], d.get('password', ''), d['encryption'])
    elif qr_type == 'sms':
        content = build_sms(d['phone'], d['message'])
    elif qr_type == 'email':
        content = build_email(d['email'], d.get('subject', ''), d.get('body', ''))
    elif qr_type == 'phone':
        content = build_phone(d['phone'])
    elif qr_type == 'location':
        content = build_location(d['latitude'], d['longitude'])

    if not content:
        return JsonResponse({'ok': False, 'error': 'No content to encode'})

    image = generate_qr_image(content, size=size, color=color, bg=bg, style=style)

    QRCode.objects.create(
        qr_type=qr_type, label=label, content=content,
        qr_color=color, bg_color=bg, qr_size=size,
        qr_style=style, image_b64=image,
    )

    return JsonResponse({'ok': True, 'image': image, 'content': content})


@require_GET
def history(request):
    qs = QRCode.objects.all()[:40]
    items = [{
        'id':         q.id,
        'qr_type':    q.qr_type,
        'type_label': q.get_qr_type_display(),
        'label':      q.display_label(),
        'created_at': q.created_at.strftime('%d %b %Y, %H:%M'),
        'image':      q.image_b64,
    } for q in qs]
    return JsonResponse({'ok': True, 'items': items})


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
