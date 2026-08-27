import json
import logging

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta

from .models import Plan, Subscription, StripeEvent

logger = logging.getLogger('qrapp')


def _get_or_create_sub(user):
    """
    Get or create a Subscription for a user, defaulting to the Free plan.
    The Free plan itself is expected to already exist — it's seeded once by
    migration 0002 (billing/migrations/0002_stripeevent_seed_plans.py), not
    re-created here on every call. If it's missing, that means migrations
    haven't been run, which should surface as a real error rather than being
    silently papered over with a second, divergent copy of the plan's values.
    """
    sub, created = Subscription.objects.get_or_create(
        user=user,
        defaults={'plan': Plan.objects.get(code='free'), 'status': 'active'},
    )
    return sub


# ── Pages ─────────────────────────────────────────────────────────────────────
@login_required(login_url='accounts:login')
def billing_page(request):
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
    sub = _get_or_create_sub(request.user)
    from qrapp.models import QRCode
    month_ago  = timezone.now() - timedelta(days=30)
    qr_this_month = QRCode.objects.filter(user=request.user, created_at__gte=month_ago).count()

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


def _get_or_create_stripe_customer(user, sub):
    """Reuse the Stripe Customer for this user's Subscription if one already
    exists, otherwise create one and persist its id."""
    if sub.stripe_customer_id:
        return sub.stripe_customer_id
    stripe.api_key = settings.STRIPE_SECRET_KEY
    customer = stripe.Customer.create(
        email=user.email,
        name=(user.get_full_name() or user.email),
        metadata={'user_id': str(user.id)},
    )
    sub.stripe_customer_id = customer.id
    sub.save(update_fields=['stripe_customer_id'])
    return customer.id


@login_required(login_url='accounts:login')
@require_POST
def upgrade_plan(request):
    """
    Switch plans.

    Free plans (price_monthly == 0) can be applied immediately — no payment
    is involved, so there's nothing to verify. A *paid* plan cannot be
    granted directly from this endpoint: doing so would mean the client
    alone decides it paid, which is exactly the bug this audit found. A
    real paid upgrade creates a Stripe Checkout Session and returns its URL
    for the frontend to redirect to; the plan itself is only ever actually
    applied by stripe_webhook below, once Stripe confirms payment via a
    signature-verified checkout.session.completed event. That split is the
    whole point: this endpoint can be called by anyone with any plan code,
    but it can never itself grant a paid plan.
    """
    try:
        payload = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    plan_code = payload.get('plan', '').strip()
    try:
        plan = Plan.objects.get(code=plan_code)
    except Plan.DoesNotExist:
        return JsonResponse({'ok': False, 'error': f'Plan "{plan_code}" not found'}, status=400)

    if plan.price_monthly > 0:
        if not settings.STRIPE_SECRET_KEY:
            return JsonResponse({
                'ok': False,
                'checkout_required': True,
                'error': 'Online checkout isn\u2019t set up in this environment yet. '
                         'Contact us to upgrade to Pro.',
            }, status=402)
        if not plan.stripe_price_id:
            logger.error('Plan %s has no stripe_price_id configured -- cannot start checkout', plan.code)
            return JsonResponse({
                'ok': False, 'checkout_required': True,
                'error': 'This plan isn\u2019t connected to a Stripe price yet. Contact support.',
            }, status=500)

        sub = _get_or_create_sub(request.user)
        stripe.api_key = settings.STRIPE_SECRET_KEY
        base_url = request.build_absolute_uri('/billing/')
        try:
            customer_id = _get_or_create_stripe_customer(request.user, sub)
            session = stripe.checkout.Session.create(
                mode='subscription',
                customer=customer_id,
                line_items=[{'price': plan.stripe_price_id, 'quantity': 1}],
                # client_reference_id / metadata are read by stripe_webhook's
                # checkout.session.completed handler to know which user and
                # plan this session was for.
                client_reference_id=str(request.user.id),
                metadata={'plan_code': plan.code, 'user_id': str(request.user.id)},
                subscription_data={'metadata': {'plan_code': plan.code, 'user_id': str(request.user.id)}},
                success_url=base_url + '?checkout=success',
                cancel_url=base_url + '?checkout=cancelled',
            )
        except stripe.error.StripeError as e:
            logger.error('Stripe checkout session creation failed for user %s: %s', request.user.id, e)
            return JsonResponse({'ok': False, 'error': 'Could not start checkout. Please try again.'}, status=502)

        # Never grant the plan here -- only return where to send the browser.
        return JsonResponse({'ok': True, 'checkout_required': True, 'checkout_url': session.url})

    # Free-tier switch — no payment involved, safe to apply directly.
    sub = _get_or_create_sub(request.user)
    sub.plan   = plan
    sub.status = 'active'
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

    # This view immediately downgrades the local record to Free, so the
    # real Stripe subscription must be cancelled too -- otherwise the
    # customer keeps being billed after the app told them they'd cancelled.
    if sub.stripe_subscription_id and settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            stripe.Subscription.cancel(sub.stripe_subscription_id)
        except stripe.error.InvalidRequestError:
            pass  # already cancelled/doesn't exist on Stripe's side — fine, proceed with local downgrade
        except stripe.error.StripeError as e:
            logger.error('Stripe subscription cancel failed for user %s: %s', request.user.id, e)
            return JsonResponse({
                'ok': False,
                'error': 'Could not cancel your subscription with the payment provider. Please try again or contact support.',
            }, status=502)

    free = Plan.objects.get(code='free')
    sub.plan   = free
    sub.status = 'canceled'
    sub.current_period_end = None
    sub.save()
    return JsonResponse({'ok': True, 'message': 'Downgraded to Free plan.'})


# ── Usage limits ────────────────────────────────────────────────────────────
def check_qr_limit(user, requested=1):
    """
    Return (allowed: bool, remaining: int|None) for creating `requested` more
    QR codes this month. `requested` defaults to 1 (a single generate());
    bulk_generate() passes the size of the batch so the whole batch is
    checked against remaining quota at once, not one-by-one.
    """
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        return True, None  # no sub = free tier = 50 limit handled by plan
    max_qr = sub.plan.max_qr_per_month
    if max_qr == 0:
        return True, None  # unlimited
    from qrapp.models import QRCode
    month_ago = timezone.now() - timedelta(days=30)
    used = QRCode.objects.filter(user=user, created_at__gte=month_ago).count()
    remaining = max_qr - used
    return remaining >= requested, remaining


def reserve_qr_quota(user, requested=1):
    """
    Atomically check-and-reserve `requested` QR-code slots against the
    user's monthly quota.

    Must be called inside `transaction.atomic()`, with the caller creating
    the QRCode row(s) — and nothing else that should be rolled back on
    failure — before that transaction commits. This locks the user's
    Subscription row for the duration of the caller's transaction, so a
    second concurrent request from the same user blocks here until the
    first commits; by the time it re-checks, it will see the first
    request's newly-created rows in its `used` count. That's what prevents
    two simultaneous requests near the limit from both passing the check
    and jointly exceeding it. It only ever contends with the same user's
    own requests — other users are unaffected.

    Returns (allowed: bool, remaining: int|None), same shape as
    check_qr_limit.
    """
    sub = _get_or_create_sub(user)
    Subscription.objects.select_for_update().get(pk=sub.pk)
    return check_qr_limit(user, requested=requested)


def check_dynamic_limit(user, requested=1):
    """
    Return (allowed: bool, remaining: int|None) for creating `requested`
    more Dynamic QR links. Unlike QR codes, dynamic links aren't a
    monthly-refreshing quota -- they're a standing resource (the redirect
    has to keep working indefinitely), so this counts ALL of the user's
    existing links, not just ones created in some recent window.
    max_dynamic_links == 0 means unlimited (same convention as
    max_qr_per_month) -- the free plan's seed data sets it to a real 0,
    i.e. the feature isn't available at all on that plan.
    """
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        return True, None
    max_links = sub.plan.max_dynamic_links
    if max_links == 0:
        return True, None  # unlimited
    from qrapp.models import DynamicLink
    used = DynamicLink.objects.filter(user=user).count()
    remaining = max_links - used
    return remaining >= requested, remaining


def reserve_dynamic_quota(user, requested=1):
    """Same atomic locking pattern as reserve_qr_quota, for Dynamic QR
    links. Must be called inside transaction.atomic(), with the caller
    creating the DynamicLink row(s) before that transaction commits."""
    sub = _get_or_create_sub(user)
    Subscription.objects.select_for_update().get(pk=sub.pk)
    return check_dynamic_limit(user, requested=requested)


# ── Stripe webhook ──────────────────────────────────────────────────────────
@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Authoritative source of truth for paid subscription state -- this is the
    ONLY place a Subscription is ever set to a paid plan. Never trust a
    client request for that; only a signature-verified event from Stripe.

    Fails closed: if STRIPE_WEBHOOK_SECRET isn't configured, or the signature
    doesn't check out, the event is rejected (400) rather than silently
    accepted. Uses stripe.Webhook.construct_event (the official SDK's
    verification, now that `stripe` is an actual dependency) instead of a
    hand-rolled HMAC check -- same algorithm either way, but this is less
    custom-crypto surface to maintain.
    """
    payload    = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error('Stripe webhook received but STRIPE_WEBHOOK_SECRET is not configured — rejecting.')
        return JsonResponse({'error': 'Webhook not configured'}, status=400)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        logger.warning('Stripe webhook rejected: %s', e)
        return JsonResponse({'error': 'Invalid payload or signature'}, status=400)

    event_id   = event['id']
    event_type = event['type']
    if not event_id:
        return JsonResponse({'error': 'Missing event id'}, status=400)

    # Idempotency: Stripe may redeliver the same event more than once
    # (retries on timeout/5xx). Only ever apply it the first time.
    _, created = StripeEvent.objects.get_or_create(
        id=event_id, defaults={'event_type': event_type},
    )
    if not created:
        return HttpResponse(status=200)  # already processed — ack without reapplying

    data = (event.get('data') or {}).get('object') or {}

    if event_type == 'checkout.session.completed':
        # client_reference_id and metadata.plan_code are set when the
        # session is created in upgrade_plan() above.
        user_id   = data.get('client_reference_id')
        plan_code = (data.get('metadata') or {}).get('plan_code')
        stripe_customer_id     = data.get('customer', '')
        stripe_subscription_id = data.get('subscription', '')
        if user_id and plan_code:
            try:
                plan = Plan.objects.get(code=plan_code)
                sub  = Subscription.objects.select_related('plan').get(user_id=user_id)
                sub.plan   = plan
                sub.status = 'active'
                sub.stripe_customer_id     = stripe_customer_id or sub.stripe_customer_id
                sub.stripe_subscription_id = stripe_subscription_id or sub.stripe_subscription_id
                sub.save()
            except (Plan.DoesNotExist, Subscription.DoesNotExist):
                logger.error('checkout.session.completed for unknown user/plan: %r', data)

    elif event_type in ('customer.subscription.updated', 'customer.subscription.deleted'):
        stripe_subscription_id = data.get('id', '')
        status = data.get('status', '')
        try:
            sub = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        except Subscription.DoesNotExist:
            logger.warning('Subscription event for unknown stripe_subscription_id: %s', stripe_subscription_id)
        else:
            if event_type == 'customer.subscription.deleted' or status in ('canceled', 'unpaid'):
                sub.plan   = Plan.objects.get(code='free')
                sub.status = 'canceled'
                sub.current_period_end = None
            else:
                sub.status = {'active': 'active', 'trialing': 'trialing',
                               'past_due': 'past_due'}.get(status, sub.status)
                period_end = data.get('current_period_end')
                if period_end:
                    from django.utils.dateparse import parse_datetime
                    import datetime
                    sub.current_period_end = datetime.datetime.fromtimestamp(
                        period_end, tz=datetime.timezone.utc)
            sub.save()

    return HttpResponse(status=200)
