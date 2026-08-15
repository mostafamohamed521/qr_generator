"""
tests.py — billing app test suite
Run: python manage.py test billing -v 2
"""
import json
import time
import hashlib
import hmac
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from .models import Plan, Subscription, StripeEvent


def make_stripe_signature(payload: bytes, secret: str) -> str:
    """Build a real Stripe-format Stripe-Signature header for a payload, so
    webhook tests exercise the actual construct_event() verification path
    rather than mocking it away entirely."""
    ts = int(time.time())
    signed = f'{ts}.'.encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f't={ts},v1={sig}'


class BillingTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('bill@example.com', 'bill@example.com', 'pass12345')
        self.c.login(username='bill@example.com', password='pass12345')

    def test_visiting_billing_page_creates_free_subscription(self):
        self.c.get('/billing/')
        self.assertTrue(Subscription.objects.filter(user=self.user, plan__code='free').exists())

    def test_current_plan_defaults_to_free(self):
        r = self.c.get('/billing/api/current/')
        d = r.json()
        self.assertEqual(d['subscription']['plan_code'], 'free')
        self.assertEqual(d['subscription']['max_qr'], 50)

    def test_upgrade_to_invalid_plan_fails(self):
        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'enterprise'}),
                         content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_cancel_when_already_free_fails(self):
        r = self.c.post('/billing/api/cancel/')
        self.assertFalse(r.json()['ok'])

    def test_billing_requires_login(self):
        c2 = Client()
        r = c2.get('/billing/')
        self.assertEqual(r.status_code, 302)

    # --- these are about behavior *given* an existing Pro subscription,
    # not about how someone gets onto Pro -- set it up directly rather than
    # through the (now Stripe-gated) upgrade endpoint. ---

    def test_cancel_downgrades_to_free(self):
        pro = Plan.objects.get(code='pro')
        Subscription.objects.create(user=self.user, plan=pro, status='active')
        r = self.c.post('/billing/api/cancel/')
        self.assertTrue(r.json()['ok'])
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'free')

    def test_pro_plan_allows_team_and_api(self):
        pro = Plan.objects.get(code='pro')
        Subscription.objects.create(user=self.user, plan=pro, status='active')
        r = self.c.get('/billing/api/current/')
        d = r.json()['subscription']
        self.assertTrue(d['allows_team'])
        self.assertTrue(d['allows_api'])


@override_settings(STRIPE_SECRET_KEY='')
class UpgradeWithoutStripeConfiguredTests(TestCase):
    """Default state of this project: no Stripe keys set at all."""

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('nostripe@example.com', 'nostripe@example.com', 'pass12345')
        self.c.login(username='nostripe@example.com', password='pass12345')

    def test_upgrade_to_paid_plan_returns_checkout_required_not_success(self):
        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}), content_type='application/json')
        d = r.json()
        self.assertEqual(r.status_code, 402)
        self.assertFalse(d['ok'])
        self.assertTrue(d['checkout_required'])
        # the actual bug this whole audit started from: must NOT have granted the plan
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'free')

    def test_upgrade_to_free_still_works_directly(self):
        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'free'}), content_type='application/json')
        self.assertTrue(r.json()['ok'])


@override_settings(STRIPE_SECRET_KEY='sk_test_fake')
class UpgradeWithStripeConfiguredTests(TestCase):
    """Stripe API calls are mocked -- no real network/keys available to
    actually reach Stripe from here."""

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('stripeuser@example.com', 'stripeuser@example.com', 'pass12345')
        self.c.login(username='stripeuser@example.com', password='pass12345')
        self.pro = Plan.objects.get(code='pro')
        self.pro.stripe_price_id = 'price_fake123'
        self.pro.save()

    @patch('billing.views.stripe.checkout.Session.create')
    @patch('billing.views.stripe.Customer.create')
    def test_upgrade_creates_checkout_session_and_does_not_grant_plan(self, mock_customer_create, mock_session_create):
        mock_customer_create.return_value = MagicMock(id='cus_fake123')
        mock_session_create.return_value = MagicMock(url='https://checkout.stripe.com/pay/cs_fake123')

        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}), content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['checkout_url'], 'https://checkout.stripe.com/pay/cs_fake123')

        # Still free -- creating a checkout session must never itself grant the plan.
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'free')
        self.assertEqual(sub.stripe_customer_id, 'cus_fake123')

        # Correct session shape was requested
        _, kwargs = mock_session_create.call_args
        self.assertEqual(kwargs['mode'], 'subscription')
        self.assertEqual(kwargs['client_reference_id'], str(self.user.id))
        self.assertEqual(kwargs['metadata']['plan_code'], 'pro')
        self.assertEqual(kwargs['line_items'][0]['price'], 'price_fake123')

    def test_upgrade_without_stripe_price_id_fails_clearly(self):
        self.pro.stripe_price_id = ''
        self.pro.save()
        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}), content_type='application/json')
        d = r.json()
        self.assertFalse(d['ok'])
        self.assertEqual(r.status_code, 500)

    @patch('billing.views.stripe.checkout.Session.create')
    @patch('billing.views.stripe.Customer.create')
    def test_existing_stripe_customer_id_is_reused(self, mock_customer_create, mock_session_create):
        Subscription.objects.create(user=self.user, plan=Plan.objects.get(code='free'),
                                     stripe_customer_id='cus_already_exists')
        mock_session_create.return_value = MagicMock(url='https://checkout.stripe.com/pay/cs_x')

        self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}), content_type='application/json')

        mock_customer_create.assert_not_called()
        _, kwargs = mock_session_create.call_args
        self.assertEqual(kwargs['customer'], 'cus_already_exists')


@override_settings(STRIPE_WEBHOOK_SECRET='whsec_fake_secret')
class StripeWebhookTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('webhookuser@example.com', 'webhookuser@example.com', 'pass12345')
        Subscription.objects.create(user=self.user, plan=Plan.objects.get(code='free'))

    def _post(self, body_dict, secret='whsec_fake_secret'):
        body = json.dumps(body_dict).encode()
        sig = make_stripe_signature(body, secret)
        return self.c.post('/billing/api/stripe-webhook/', data=body,
                            content_type='application/json', HTTP_STRIPE_SIGNATURE=sig)

    def test_rejects_when_secret_not_configured(self):
        with self.settings(STRIPE_WEBHOOK_SECRET=''):
            r = self._post({'id': 'evt_1', 'type': 'checkout.session.completed', 'data': {'object': {}}})
        self.assertEqual(r.status_code, 400)

    def test_rejects_bad_signature(self):
        r = self._post({'id': 'evt_1', 'type': 'checkout.session.completed', 'data': {'object': {}}},
                        secret='whsec_wrong_secret')
        self.assertEqual(r.status_code, 400)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'free')  # unchanged

    def test_checkout_completed_grants_plan(self):
        pro = Plan.objects.get(code='pro')
        r = self._post({
            'id': 'evt_test_1', 'type': 'checkout.session.completed',
            'data': {'object': {
                'client_reference_id': str(self.user.id),
                'metadata': {'plan_code': 'pro'},
                'customer': 'cus_abc', 'subscription': 'sub_abc',
            }},
        })
        self.assertEqual(r.status_code, 200)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'pro')
        self.assertEqual(sub.status, 'active')
        self.assertEqual(sub.stripe_subscription_id, 'sub_abc')

    def test_duplicate_event_applied_only_once(self):
        pro = Plan.objects.get(code='pro')
        event = {
            'id': 'evt_dup_1', 'type': 'checkout.session.completed',
            'data': {'object': {
                'client_reference_id': str(self.user.id),
                'metadata': {'plan_code': 'pro'},
                'customer': 'cus_x', 'subscription': 'sub_x',
            }},
        }
        r1 = self._post(event)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(StripeEvent.objects.filter(id='evt_dup_1').count(), 1)

        # simulate a manual downgrade in between, to prove the second delivery is a no-op
        sub = Subscription.objects.get(user=self.user)
        sub.plan = Plan.objects.get(code='free')
        sub.save()

        r2 = self._post(event)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(StripeEvent.objects.filter(id='evt_dup_1').count(), 1)  # still just one
        sub.refresh_from_db()
        self.assertEqual(sub.plan.code, 'free')  # NOT re-applied

    def test_subscription_deleted_downgrades_to_free(self):
        pro = Plan.objects.get(code='pro')
        sub = Subscription.objects.get(user=self.user)
        sub.plan = pro
        sub.status = 'active'
        sub.stripe_subscription_id = 'sub_to_cancel'
        sub.save()

        r = self._post({
            'id': 'evt_cancel_1', 'type': 'customer.subscription.deleted',
            'data': {'object': {'id': 'sub_to_cancel', 'status': 'canceled'}},
        })
        self.assertEqual(r.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.plan.code, 'free')
        self.assertEqual(sub.status, 'canceled')
