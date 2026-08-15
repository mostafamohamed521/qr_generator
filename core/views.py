import json
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST

from .models import ContactMessage

ICONS = {
    'grid':   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>',
    'sliders':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/></svg>',
    'chart':  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>',
    'layers': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><rect x="2" y="3" width="20" height="4" rx="1"/><rect x="2" y="10" width="20" height="4" rx="1"/><rect x="2" y="17" width="20" height="4" rx="1"/></svg>',
    'users':  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    'code':   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="w-5 h-5"><path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/></svg>',
}


def _features():
    return [
        {'icon': ICONS['grid'], 'title': 'All QR types', 'desc': 'URL, text, contact cards, WiFi, SMS, email, phone, and location — all in one generator.'},
        {'icon': ICONS['sliders'], 'title': 'Full customization', 'desc': 'Colors, shapes, sizes, and your own logo embedded right in the code.'},
        {'icon': ICONS['chart'], 'title': 'Analytics & tracking', 'desc': 'See scan counts and activity trends for every code you create.'},
        {'icon': ICONS['layers'], 'title': 'Bulk generation', 'desc': 'Upload a list and generate hundreds of codes in one click, exported as a ZIP.'},
        {'icon': ICONS['users'], 'title': 'Built for teams', 'desc': 'Shared workspaces, roles, and an activity log for everyone on the team.'},
        {'icon': ICONS['code'], 'title': 'Developer API', 'desc': 'Generate and manage QR codes programmatically with API keys and webhooks.'},
    ]


def _testimonials():
    return [
        {'quote': 'We switched all our print campaigns to QR Forge — the analytics alone paid for itself.', 'name': 'Mariam K.', 'role': 'Marketing Lead'},
        {'quote': 'The bulk generator saved us a full day of manual work for our event badges.', 'name': 'Omar S.', 'role': 'Event Organizer'},
        {'quote': 'Clean, fast, and the API made it trivial to plug into our own app.', 'name': 'Lina F.', 'role': 'Indie Developer'},
    ]


def landing(request):
    return render(request, 'core/landing.html', {'features': _features(), 'testimonials': _testimonials()})


def pricing(request):
    return render(request, 'core/pricing.html')


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    return render(request, 'core/contact.html')


@require_POST
def contact_submit(request):
    """
    Real handler for the contact form -- previously the frontend faked a
    success toast without ever submitting anything (found during a
    site-wide page audit). Always saves the message (the durable record);
    the notification email is best-effort and never blocks that save.
    """
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid request.'}, status=400)

    email   = payload.get('email', '').strip()
    message = payload.get('message', '').strip()

    if not email or not message:
        return JsonResponse({'ok': False, 'error': 'Please fill in both fields.'}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'That doesn\u2019t look like a valid email.'}, status=400)
    if len(message) > 4000:
        return JsonResponse({'ok': False, 'error': 'Message is too long.'}, status=400)

    ContactMessage.objects.create(email=email, message=message)

    notify_to = getattr(settings, 'CONTACT_NOTIFY_EMAIL', '')
    if notify_to:
        try:
            send_mail(
                subject=f'New contact form message from {email}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notify_to],
                fail_silently=True,  # the message is already saved; don't fail the request over email delivery
            )
        except BadHeaderError:
            pass

    return JsonResponse({'ok': True, 'message': 'Message sent! We will reply within 24h.'})


def faq(request):
    faqs = [
        {'q': 'Is QR Forge free to use?', 'a': 'Yes — the Free plan covers up to 50 QR codes a month, no credit card needed.'},
        {'q': 'Can I customize the QR code design?', 'a': 'Yes, you can set colors, shapes, size, and add your own logo.'},
        {'q': 'Do you support teams?', 'a': 'Yes, the Pro plan includes shared team workspaces with roles.'},
        {'q': 'Can I change where a QR code points after printing it?', 'a': 'Yes, with Dynamic QR codes (Pro) you can update the destination URL anytime without reprinting.'},
        {'q': 'Is there an API?', 'a': 'Yes, Pro and Team plans include API keys and webhooks for programmatic access.'},
    ]
    return render(request, 'core/faq.html', {'faqs': faqs})


from django.http import HttpResponse


def robots_txt(request):
    content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /app/api/
Disallow: /teams/api/
Sitemap: https://yoursite.com/sitemap.xml
"""
    return HttpResponse(content, content_type='text/plain')


def sitemap_xml(request):
    base = request.build_absolute_uri('/')[:-1]
    pages = ['', '/pricing/', '/about/', '/faq/', '/contact/']
    urls = '\n'.join(f'  <url><loc>{base}{p}</loc></url>' for p in pages)
    content = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>'
    return HttpResponse(content, content_type='application/xml')
