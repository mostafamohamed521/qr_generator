"""
tests.py — billing app test suite
Run: python manage.py test billing -v 2
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Plan, Subscription


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

    def test_upgrade_to_pro(self):
        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}),
                         content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'pro')
        self.assertIsNotNone(sub.current_period_end)

    def test_upgrade_to_invalid_plan_fails(self):
        r = self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'enterprise'}),
                         content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_cancel_downgrades_to_free(self):
        self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}), content_type='application/json')
        r = self.c.post('/billing/api/cancel/')
        self.assertTrue(r.json()['ok'])
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan.code, 'free')

    def test_cancel_when_already_free_fails(self):
        r = self.c.post('/billing/api/cancel/')
        self.assertFalse(r.json()['ok'])

    def test_pro_plan_allows_team_and_api(self):
        self.c.post('/billing/api/upgrade/', json.dumps({'plan': 'pro'}), content_type='application/json')
        r = self.c.get('/billing/api/current/')
        d = r.json()['subscription']
        self.assertTrue(d['allows_team'])
        self.assertTrue(d['allows_api'])

    def test_billing_requires_login(self):
        c2 = Client()
        r = c2.get('/billing/')
        self.assertEqual(r.status_code, 302)
