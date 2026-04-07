from django.shortcuts import render
from django.http import JsonResponse
from .forms import *
from .qr_utils import QRGenerator
from .models import QRHistory

def index(request):
    return render(request, 'index.html')

def generate_qr(request):
    if request.method == 'POST':
        qr_type = request.POST.get('type', 'url')
        qr_image = None
        content = ''
        
        if qr_type == 'url':
            form = URLForm(request.POST)
            if form.is_valid():
                url = form.cleaned_data['url']
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                content = url
                qr_image = QRGenerator.generate_qr(content)
                
        elif qr_type == 'text':
            form = TextForm(request.POST)
            if form.is_valid():
                content = form.cleaned_data['text']
                qr_image = QRGenerator.generate_qr(content)
                
        elif qr_type == 'contact':
            form = ContactForm(request.POST)
            if form.is_valid():
                content = QRGenerator.generate_vcard(form.cleaned_data)
                qr_image = QRGenerator.generate_qr(content)
                
        elif qr_type == 'wifi':
            form = WiFiForm(request.POST)
            if form.is_valid():
                content = QRGenerator.generate_wifi_qr(
                    form.cleaned_data['ssid'],
                    form.cleaned_data['password'],
                    form.cleaned_data['encryption']
                )
                qr_image = QRGenerator.generate_qr(content)
                
        elif qr_type == 'sms':
            form = SMSForm(request.POST)
            if form.is_valid():
                content = QRGenerator.generate_sms_qr(
                    form.cleaned_data['phone'],
                    form.cleaned_data['message']
                )
                qr_image = QRGenerator.generate_qr(content)
                
        elif qr_type == 'email':
            form = EmailForm(request.POST)
            if form.is_valid():
                content = QRGenerator.generate_email_qr(
                    form.cleaned_data['email'],
                    form.cleaned_data['subject'],
                    form.cleaned_data['body']
                )
                qr_image = QRGenerator.generate_qr(content)
        
        # Save to database
        if content:
            QRHistory.objects.create(qr_type=qr_type, content=content)
        
        return JsonResponse({
            'success': True,
            'qr_image': qr_image,
            'content': content
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

def get_history(request):
    history = QRHistory.objects.all().order_by('-created_at')[:20]
    data = [{
        'id': h.id,
        'type': h.get_qr_type_display(),
        'created_at': h.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for h in history]
    return JsonResponse({'history': data})

def delete_history(request, id):
    try:
        QRHistory.objects.get(id=id).delete()
        return JsonResponse({'success': True})
    except:
        return JsonResponse({'success': False})