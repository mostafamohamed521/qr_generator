"""
tests.py — api app test suite (public REST API + webhooks)
Run: python manage.py test api -v 2
"""
import json
import hashlib
import hmac
import threading
import http.server
import time
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import APIKey, WebhookEndpoint, generate_api_key, hash_api_key
from qrapp.models import QRCode, DynamicLink


def make_api_key(user, name='Test Key'):
    """
    Test helper mirroring the real create_key flow (api/views.py): generates
    a raw key, stores only its hash, and hands back (APIKey, raw_key). Bare
    APIKey.objects.create(user=..., name=...) with no key_hash would violate
    the unique constraint on key_hash the second time it's called in the
    same test run (every row would share the '' default) — this is why a
    shared helper exists instead of leaving each test to construct its own.
    """
    raw = generate_api_key()
    key = APIKey.objects.create(user=user, name=name, key_hash=hash_api_key(raw), key_prefix=raw[:14])
    return key, raw


class APIAuthTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('dev@example.com', 'dev@example.com', 'pass12345')
        self.key, self.raw_key = make_api_key(self.user)

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f'Bearer {self.raw_key}'}

    def test_no_key_returns_401(self):
        r = self.c.get('/api/v1/me/')
        self.assertEqual(r.status_code, 401)

    def test_invalid_key_returns_401(self):
        r = self.c.get('/api/v1/me/', HTTP_AUTHORIZATION='Bearer not_a_real_key')
        self.assertEqual(r.status_code, 401)

    def test_valid_key_returns_200(self):
        r = self.c.get('/api/v1/me/', **self._auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['user']['email'], 'dev@example.com')

    def test_revoked_key_rejected(self):
        self.key.is_active = False
        self.key.save()
        r = self.c.get('/api/v1/me/', **self._auth())
        self.assertEqual(r.status_code, 401)

    def test_key_updates_last_used(self):
        self.assertIsNone(self.key.last_used_at)
        self.c.get('/api/v1/me/', **self._auth())
        self.key.refresh_from_db()
        self.assertIsNotNone(self.key.last_used_at)

    def test_plaintext_key_never_returned_by_me_endpoint(self):
        """The key itself must never come back in any API response body."""
        r = self.c.get('/api/v1/me/', **self._auth())
        self.assertNotIn(self.raw_key, r.content.decode())


class APIGenerateTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('gen@example.com', 'gen@example.com', 'pass12345')
        self.key, raw = make_api_key(self.user)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {raw}'}

    def test_generate_url_qr(self):
        r = self.c.post('/api/v1/generate/',
            json.dumps({'type': 'url', 'url': 'https://example.com', 'size': 200}),
            content_type='application/json', **self.auth)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertTrue(d['image'].startswith('data:image/png;base64,'))
        self.assertTrue(QRCode.objects.filter(pk=d['id']).exists())

    def test_generate_missing_type_fields_fails(self):
        r = self.c.post('/api/v1/generate/', json.dumps({'type': 'url'}),
            content_type='application/json', **self.auth)
        self.assertEqual(r.status_code, 400)

    def test_list_qrcodes(self):
        QRCode.objects.create(user=self.user, qr_type='url', content='https://a.com')
        QRCode.objects.create(user=self.user, qr_type='text', content='hello')
        r = self.c.get('/api/v1/qrcodes/', **self.auth)
        d = r.json()
        self.assertEqual(d['total'], 2)

    def test_list_filter_by_type(self):
        QRCode.objects.create(user=self.user, qr_type='url', content='https://a.com')
        QRCode.objects.create(user=self.user, qr_type='text', content='hello')
        r = self.c.get('/api/v1/qrcodes/?type=url', **self.auth)
        self.assertEqual(r.json()['total'], 1)

    def test_get_single_qrcode(self):
        q = QRCode.objects.create(user=self.user, qr_type='url', content='https://a.com', image_b64='data:image/png;base64,x')
        r = self.c.get(f'/api/v1/qrcodes/{q.pk}/', **self.auth)
        d = r.json()
        self.assertEqual(d['item']['id'], q.pk)

    def test_get_nonexistent_qrcode_404s(self):
        r = self.c.get('/api/v1/qrcodes/99999/', **self.auth)
        self.assertEqual(r.status_code, 404)

    def test_delete_qrcode(self):
        q = QRCode.objects.create(user=self.user, qr_type='text', content='delete me')
        r = self.c.post(f'/api/v1/qrcodes/{q.pk}/delete/', **self.auth)
        self.assertTrue(r.json()['ok'])
        self.assertFalse(QRCode.objects.filter(pk=q.pk).exists())

    def test_cannot_access_another_users_qrcode(self):
        """IDOR check: an API key must not reach a QRCode owned by a different user."""
        other = User.objects.create_user('other@example.com', 'other@example.com', 'pass12345')
        q = QRCode.objects.create(user=other, qr_type='text', content='not yours')
        r = self.c.get(f'/api/v1/qrcodes/{q.pk}/', **self.auth)
        self.assertEqual(r.status_code, 404)

    def test_cannot_delete_another_users_qrcode(self):
        other = User.objects.create_user('other2@example.com', 'other2@example.com', 'pass12345')
        q = QRCode.objects.create(user=other, qr_type='text', content='not yours')
        r = self.c.post(f'/api/v1/qrcodes/{q.pk}/delete/', **self.auth)
        self.assertEqual(r.status_code, 404)
        self.assertTrue(QRCode.objects.filter(pk=q.pk).exists())  # still there — not deleted


class APIDynamicLinkTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('dyn@example.com', 'dyn@example.com', 'pass12345')
        self.key, raw = make_api_key(self.user)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {raw}'}

    def test_create_dynamic_link_via_api(self):
        r = self.c.post('/api/v1/dynamic/create/',
            json.dumps({'target_url': 'https://example.com', 'label': 'API test'}),
            content_type='application/json', **self.auth)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertIn('short_code', d['link'])

    def test_update_dynamic_link_via_api(self):
        link = DynamicLink.objects.create(user=self.user, target_url='https://old.com')
        r = self.c.post(f'/api/v1/dynamic/{link.pk}/update/',
            json.dumps({'target_url': 'https://new.com', 'is_active': False}),
            content_type='application/json', **self.auth)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['target_url'], 'https://new.com')
        self.assertFalse(d['is_active'])

    def test_list_dynamic_links_via_api(self):
        DynamicLink.objects.create(user=self.user, target_url='https://a.com')
        r = self.c.get('/api/v1/dynamic/', **self.auth)
        self.assertEqual(len(r.json()['links']), 1)

    def test_cannot_update_another_users_dynamic_link(self):
        other = User.objects.create_user('other3@example.com', 'other3@example.com', 'pass12345')
        link = DynamicLink.objects.create(user=other, target_url='https://old.com')
        r = self.c.post(f'/api/v1/dynamic/{link.pk}/update/',
            json.dumps({'target_url': 'https://hijacked.com'}),
            content_type='application/json', **self.auth)
        self.assertEqual(r.status_code, 404)
        link.refresh_from_db()
        self.assertEqual(link.target_url, 'https://old.com')  # unchanged


class APIGenerateQuotaTests(TestCase):
    """api_generate must respect the same monthly QR quota as the session
    generate() view — it must not be a way to bypass it."""

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('quota@example.com', 'quota@example.com', 'pass12345')
        self.key, raw = make_api_key(self.user)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {raw}'}
        from billing.models import Plan, Subscription
        self.plan = Plan.objects.get(code='pro')
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan, status='active')

    def _generate(self):
        return self.c.post('/api/v1/generate/',
            json.dumps({'type': 'text', 'text': 'hello'}),
            content_type='application/json', **self.auth)

    def test_blocked_once_at_limit(self):
        self.plan.max_qr_per_month = 2
        self.plan.save()
        self.assertTrue(self._generate().json()['ok'])
        self.assertTrue(self._generate().json()['ok'])
        r = self._generate()
        d = r.json()
        self.assertFalse(d['ok'])
        self.assertEqual(d['code'], 'quota_exceeded')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(QRCode.objects.filter(user=self.user).count(), 2)

    def test_unlimited_when_max_qr_is_zero(self):
        self.plan.max_qr_per_month = 0  # 0 = unlimited
        self.plan.save()
        for _ in range(5):
            self.assertTrue(self._generate().json()['ok'])
        self.assertEqual(QRCode.objects.filter(user=self.user).count(), 5)


class APIKeyManagementTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('keymgmt@example.com', 'keymgmt@example.com', 'pass12345')
        self.c.login(username='keymgmt@example.com', password='pass12345')
        # These tests are about key-management mechanics, not plan gating —
        # give the user a Pro subscription so create_key's allows_api check
        # (see test_plan_gating below for that check itself) doesn't get in
        # the way of what each test is actually verifying.
        from billing.models import Plan, Subscription
        Subscription.objects.create(user=self.user, plan=Plan.objects.get(code='pro'), status='active')

    def test_create_key(self):
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'My Key'}),
            content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertTrue(d['key']['key'].startswith('qrf_'))
        # the raw key must never be persisted in plaintext
        stored = APIKey.objects.get(pk=d['key']['id'])
        self.assertIsNone(stored.key)
        self.assertEqual(stored.key_hash, hash_api_key(d['key']['key']))

    def test_max_10_keys(self):
        for i in range(10):
            make_api_key(self.user, name=f'Key {i}')
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'One Too Many'}),
            content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_revoke_key(self):
        key, raw = make_api_key(self.user, name='ToRevoke')
        r = self.c.post(f'/api/v1/keys/{key.pk}/revoke/')
        self.assertTrue(r.json()['ok'])
        self.assertFalse(APIKey.objects.filter(pk=key.pk).exists())

    def test_docs_page_requires_login(self):
        c2 = Client()
        r = c2.get('/api/v1/docs/')
        self.assertEqual(r.status_code, 302)


class APIPlanEntitlementTests(TestCase):
    """Plan.allows_api must be enforced server-side, not just hidden in the UI."""

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('planuser@example.com', 'planuser@example.com', 'pass12345')
        self.c.login(username='planuser@example.com', password='pass12345')

    def test_free_user_cannot_create_key(self):
        # no Subscription row at all = free tier, per create_key's fallback
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'Nope'}),
            content_type='application/json')
        d = r.json()
        self.assertEqual(r.status_code, 403)
        self.assertFalse(d['ok'])
        self.assertEqual(APIKey.objects.filter(user=self.user).count(), 0)

    def test_free_plan_explicit_still_blocked(self):
        from billing.models import Plan, Subscription
        Subscription.objects.create(user=self.user, plan=Plan.objects.get(code='free'), status='active')
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'Nope'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 403)

    def test_pro_user_can_create_key(self):
        from billing.models import Plan, Subscription
        Subscription.objects.create(user=self.user, plan=Plan.objects.get(code='pro'), status='active')
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'Yes'}),
            content_type='application/json')
        self.assertTrue(r.json()['ok'])


class WebhookDispatchTests(TestCase):
    """Integration test: spins up a real local HTTP server to receive the webhook.

    The local test server only speaks plain HTTP on 127.0.0.1, which the SSRF
    guard (api/webhooks.py) correctly refuses to deliver to by default —
    that's exactly what it's for. These tests patch validate_webhook_url /
    _is_public_ip to exercise the real delivery transport (signing, headers,
    timeout, connection handling) against the local server without weakening
    the guard itself; see APIWebhookSSRFTests below for tests of the guard
    with no patching, which is what actually proves the protection works.
    """

    def test_webhook_fires_with_valid_signature_on_scan(self):
        from . import webhooks as wh_module
        from .webhooks import fire_event

        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                received.append({
                    'body': json.loads(body),
                    'signature': self.headers.get('X-QRForge-Signature'),
                })
                self.send_response(200)
                self.end_headers()
            def log_message(self, *a): pass

        server = http.server.HTTPServer(('127.0.0.1', 9797), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            user = User.objects.create_user('wh@example.com', 'wh@example.com', 'pass12345')
            WebhookEndpoint.objects.create(
                user=user, target_url='http://127.0.0.1:9797/hook',
                event='qr.scanned', secret='test_secret',
            )
            with patch.object(wh_module, 'validate_webhook_url', lambda url: None), \
                 patch.object(wh_module, '_is_public_ip', lambda ip: True):
                fire_event('qr.scanned', {'short_code': 'abc123', 'target_url': 'https://example.com'})
                time.sleep(1.0)

            self.assertEqual(len(received), 1)
            body_bytes = json.dumps(received[0]['body']).encode()
            expected_sig = hmac.new(b'test_secret', body_bytes, hashlib.sha256).hexdigest()
            self.assertEqual(received[0]['signature'], expected_sig)
        finally:
            server.shutdown()

    def test_no_active_webhooks_does_not_error(self):
        from .webhooks import fire_event
        # Should simply no-op without raising
        fire_event('qr.scanned', {'short_code': 'xyz'})

    def test_inactive_webhook_not_fired(self):
        from .webhooks import fire_event
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(True)
                self.send_response(200)
                self.end_headers()
            def log_message(self, *a): pass

        server = http.server.HTTPServer(('127.0.0.1', 9798), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            user = User.objects.create_user('wh2@example.com', 'wh2@example.com', 'pass12345')
            WebhookEndpoint.objects.create(
                user=user, target_url='http://127.0.0.1:9798/hook',
                event='qr.scanned', secret='x', is_active=False,
            )
            # is_active=False means fire_event's own queryset filter excludes
            # this endpoint before delivery is even attempted — no need to
            # patch the SSRF guard for this one, it should never get that far.
            fire_event('qr.scanned', {'short_code': 'xyz'})
            time.sleep(0.5)
            self.assertEqual(len(received), 0)
        finally:
            server.shutdown()


class APIWebhookSSRFTests(TestCase):
    """SSRF guard tests — deliberately NOT patched, this is what proves the
    protection actually works rather than just exists."""

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('ssrf@example.com', 'ssrf@example.com', 'pass12345')
        from billing.models import Plan, Subscription
        Subscription.objects.create(user=self.user, plan=Plan.objects.get(code='pro'), status='active')
        self.c.login(username='ssrf@example.com', password='pass12345')

    def _create(self, url):
        return self.c.post('/api/v1/webhooks/create/', json.dumps({'target_url': url, 'event': 'qr.scanned'}),
            content_type='application/json')

    def test_rejects_localhost(self):
        r = self._create('https://localhost/hook')
        self.assertFalse(r.json()['ok'])
        self.assertEqual(WebhookEndpoint.objects.count(), 0)

    def test_rejects_loopback_ip(self):
        r = self._create('https://127.0.0.1/hook')
        self.assertFalse(r.json()['ok'])

    def test_rejects_private_ipv4(self):
        for ip in ('10.0.0.1', '172.16.0.1', '192.168.1.1'):
            r = self._create(f'https://{ip}/hook')
            self.assertFalse(r.json()['ok'], f'{ip} should have been rejected')

    def test_rejects_cloud_metadata_endpoint(self):
        r = self._create('https://169.254.169.254/latest/meta-data/')
        self.assertFalse(r.json()['ok'])

    def test_rejects_link_local_ipv6(self):
        r = self._create('https://[fe80::1]/hook')
        self.assertFalse(r.json()['ok'])

    def test_rejects_non_https_scheme(self):
        r = self._create('http://example.com/hook')
        self.assertFalse(r.json()['ok'])

    def test_rejects_unresolvable_host(self):
        r = self._create('https://this-domain-should-not-exist-qrforge-test.invalid/hook')
        self.assertFalse(r.json()['ok'])

    def test_accepts_legitimate_public_https_url(self):
        """
        Not run against the real network (no network access in CI/this
        sandbox, and we don't want tests depending on an external service
        being up) — instead verifies the validator's actual DNS-resolution
        path against a known-public IP by patching only getaddrinfo's
        result, not the public/private classification logic itself.
        """
        from . import webhooks as wh_module
        with patch.object(wh_module.socket, 'getaddrinfo',
                           return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]):
            r = self._create('https://example.com/hook')
        self.assertTrue(r.json()['ok'])
        self.assertEqual(WebhookEndpoint.objects.filter(user=self.user).count(), 1)

    def test_redirect_response_is_not_followed(self):
        """
        A webhook target that returns a 3xx must not be followed — http.client
        (used for delivery) never auto-follows redirects, unlike
        urllib.request.urlopen. This verifies delivery treats a redirect as a
        failed/no-op delivery rather than chasing the Location header.
        """
        from . import webhooks as wh_module

        hit_paths = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                hit_paths.append(self.path)
                if self.path == '/redirect-me':
                    self.send_response(302)
                    self.send_header('Location', 'http://127.0.0.1:9799/internal-secret')
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.end_headers()
            def log_message(self, *a): pass

        server = http.server.HTTPServer(('127.0.0.1', 9799), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(wh_module, 'validate_webhook_url', lambda url: None), \
                 patch.object(wh_module, '_is_public_ip', lambda ip: True):
                wh_module._deliver('http://127.0.0.1:9799/redirect-me', 'secret', {'event': 'test'})
            # only the original path should ever have been hit — the redirect
            # target must never be requested
            self.assertEqual(hit_paths, ['/redirect-me'])
        finally:
            server.shutdown()
