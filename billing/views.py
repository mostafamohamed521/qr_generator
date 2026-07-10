import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Plan, Subscription


def _get_or_create_sub(user):
    """Get or create a Free subscription for a user."""
    sub, created = Subscription.objects.get_or_create(
        user=user,
        defaults={
            'plan': Plan.objects.get_or_create(
                code='free',
                defaults={
                    'name': 'Free',
                    'price_monthly': 0,
                    'max_qr_per_month': 50,
                    'max_dynamic_links': 0,
                    'allows_team': False,
                    'allows_api': False,
                }
            )[0],
            'status': 'active',
        }
    )
    return sub


def _ensure_plans():
    """Seed Free and Pro plans if they don't exist."""
    Plan.objects.get_or_create(
        code='free',
        defaults={
            'name': 'Free', 'price_monthly': 0,
            'max_qr_per_month': 50, 'max_dynamic_links': 0,
            'allows_team': False, 'allows_api': False,
        }
    )
    Plan.objects.get_or_create(
        code='pro',
        defaults={
            'name': 'Pro', 'price_monthly': 12,
            'max_qr_per_month': 0,  # 0 = unlimited
            'max_dynamic_links': 0,  # 0 = unlimited
            'allows_team': True, 'allows_api': True,
        }
    )


# ── Pages ─────────────────────────────────────────────────────────────────────
@login_required(login_url='accounts:login')
def billing_page(request):
    _ensure_plans()
    sub  = _get_or_create_sub(request.user)
    plans = Plan.objects.all().order_by('price_monthly')
    comparison = [
        {'feature': 'QR codes per month',   'free': '50',        'pro': 'Unlimited'},
        {'feature': 'Dynamic QR codes',      'free': '—',         'pro': 'Unlimited'},
        {'feature': 'Custom QR colors & logo','free':'✓',         'pro': '✓'},
        {'feature': 'Bulk generation',        'free':'Up to 50',  'pro': 'Up to 200'},
        {'feature': 'SVG / JPG export',       'free':'✓',         'pro': '✓'},
        {'feature': 'Scan analytics',         'free':'Basic',     'pro': 'Full (14 days)'},
        {'feature': 'Team collaboration',     'free':'—',         'pro': '✓'},
        {'feature': 'API access',             'free':'—',         'pro': '✓'},
        {'feature': 'Webhooks',               'free':'—',         'pro': '✓'},
        {'feature': 'CSV export',             'free':'✓',         'pro': '✓'},
        {'feature': 'Priority support',       'free':'—',         'pro': '✓'},
    ]
    return render(request, 'billing/billing.html', {'sub': sub, 'plans': plans, 'comparison': comparison})


# ── API ───────────────────────────────────────────────────────────────────────
@login_required(login_url='accounts:login')
@require_GET
def current_plan(request):
    _ensure_plans()
    sub = _get_or_create_sub(request.user)
    from qrapp.models import QRCode, DynamicLink
    from django.utils.timezone import now
    from datetime import timedelta
    month_ago  = now() - timedelta(days=30)
    qr_this_month = QRCode.objects.filter(created_at__gte=month_ago).count()

    return JsonResponse({'ok': True, 'subscription': {
        'plan_code':    sub.plan.code,
        'plan_name':    sub.plan.name,
        'price':        float(sub.plan.price_monthly),
        'status':       sub.status,
        'max_qr':       sub.plan.max_qr_per_month,
        'max_dynamic':  sub.plan.max_dynamic_links,
        'allows_team':  sub.plan.allows_team,
        'allows_api':   sub.plan.allows_api,
        'qr_this_month': qr_this_month,
        'period_end':   sub.current_period_end.strftime('%d %b %Y') if sub.current_period_end else None,
    }})


@login_required(login_url='accounts:login')
@require_POST
def upgrade_plan(request):
    """Simulated upgrade — real Stripe checkout wired here in production."""
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    plan_code = payload.get('plan', '').strip()
    _ensure_plans()
    try:
        plan = Plan.objects.get(code=plan_code)
    except Plan.DoesNotExist:
        return JsonResponse({'ok': False, 'error': f'Plan "{plan_code}" not found'}, status=400)

    sub = _get_or_create_sub(request.user)
    sub.plan   = plan
    sub.status = 'active'
    if plan.code == 'pro':
        sub.current_period_end = timezone.now() + timezone.timedelta(days=30)
    else:
        sub.current_period_end = None
    sub.save()

    return JsonResponse({'ok': True, 'plan': plan.code, 'plan_name': plan.name,
                         'message': f'Switched to {plan.name} plan.'})


@login_required(login_url='accounts:login')
@require_POST
def cancel_plan(request):
    sub = _get_or_create_sub(request.user)
    if sub.plan.code == 'free':
        return JsonResponse({'ok': False, 'error': 'Already on Free plan'}, status=400)
    free = Plan.objects.get(code='free')
    sub.plan   = free
    sub.status = 'canceled'
    sub.current_period_end = None
    sub.save()
    return JsonResponse({'ok': True, 'message': 'Downgraded to Free plan.'})


# ── Usage limits helper (used by generate/bulk views) ─────────────────────────
def check_qr_limit(user):
    """Return (allowed: bool, remaining: int|None)."""
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        return True, None  # no sub = free tier = 50 limit handled by plan
    max_qr = sub.plan.max_qr_per_month
    if max_qr == 0:
        return True, None  # unlimited
    from qrapp.models import QRCode
    from datetime import timedelta
    month_ago = timezone.now() - timedelta(days=30)
    used = QRCode.objects.filter(created_at__gte=month_ago).count()
    remaining = max_qr - used
    return remaining > 0, remaining


# ── Stripe webhook endpoint (placeholder) ─────────────────────────────────────
@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Production: verify Stripe signature, handle events.
    Supported events to implement: customer.subscription.updated,
    customer.subscription.deleted, invoice.payment_succeeded.
    """
    payload = request.body
    sig     = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    # TODO: stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    # For now just acknowledge
    return HttpResponse(status=200)


def billing_context(request):
    """Used by billing_page to pass comparison table."""
    pass
