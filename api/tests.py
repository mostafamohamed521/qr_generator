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
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import APIKey, WebhookEndpoint
from qrapp.models import QRCode, DynamicLink


class APIAuthTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('dev@example.com', 'dev@example.com', 'pass12345')
        self.key = APIKey.objects.create(user=self.user, name='Test Key')

    def _auth(self):
        return {'HTTP_AUTHORIZATION': f'Bearer {self.key.key}'}

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


class APIGenerateTests(TestCase):

    def setUp(self):
        self.c = Client()
        user = User.objects.create_user('gen@example.com', 'gen@example.com', 'pass12345')
        self.key = APIKey.objects.create(user=user, name='Key')
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.key.key}'}

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
        QRCode.objects.create(qr_type='url', content='https://a.com')
        QRCode.objects.create(qr_type='text', content='hello')
        r = self.c.get('/api/v1/qrcodes/', **self.auth)
        d = r.json()
        self.assertEqual(d['total'], 2)

    def test_list_filter_by_type(self):
        QRCode.objects.create(qr_type='url', content='https://a.com')
        QRCode.objects.create(qr_type='text', content='hello')
        r = self.c.get('/api/v1/qrcodes/?type=url', **self.auth)
        self.assertEqual(r.json()['total'], 1)

    def test_get_single_qrcode(self):
        q = QRCode.objects.create(qr_type='url', content='https://a.com', image_b64='data:image/png;base64,x')
        r = self.c.get(f'/api/v1/qrcodes/{q.pk}/', **self.auth)
        d = r.json()
        self.assertEqual(d['item']['id'], q.pk)

    def test_get_nonexistent_qrcode_404s(self):
        r = self.c.get('/api/v1/qrcodes/99999/', **self.auth)
        self.assertEqual(r.status_code, 404)

    def test_delete_qrcode(self):
        q = QRCode.objects.create(qr_type='text', content='delete me')
        r = self.c.post(f'/api/v1/qrcodes/{q.pk}/delete/', **self.auth)
        self.assertTrue(r.json()['ok'])
        self.assertFalse(QRCode.objects.filter(pk=q.pk).exists())


class APIDynamicLinkTests(TestCase):

    def setUp(self):
        self.c = Client()
        user = User.objects.create_user('dyn@example.com', 'dyn@example.com', 'pass12345')
        self.key = APIKey.objects.create(user=user, name='Key')
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.key.key}'}

    def test_create_dynamic_link_via_api(self):
        r = self.c.post('/api/v1/dynamic/create/',
            json.dumps({'target_url': 'https://example.com', 'label': 'API test'}),
            content_type='application/json', **self.auth)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertIn('short_code', d['link'])

    def test_update_dynamic_link_via_api(self):
        link = DynamicLink.objects.create(target_url='https://old.com')
        r = self.c.post(f'/api/v1/dynamic/{link.pk}/update/',
            json.dumps({'target_url': 'https://new.com', 'is_active': False}),
            content_type='application/json', **self.auth)
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['target_url'], 'https://new.com')
        self.assertFalse(d['is_active'])

    def test_list_dynamic_links_via_api(self):
        DynamicLink.objects.create(target_url='https://a.com')
        r = self.c.get('/api/v1/dynamic/', **self.auth)
        self.assertEqual(len(r.json()['links']), 1)


class APIKeyManagementTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('keymgmt@example.com', 'keymgmt@example.com', 'pass12345')
        self.c.login(username='keymgmt@example.com', password='pass12345')

    def test_create_key(self):
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'My Key'}),
            content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertTrue(d['key']['key'].startswith('qrf_'))

    def test_max_10_keys(self):
        for i in range(10):
            APIKey.objects.create(user=self.user, name=f'Key {i}')
        r = self.c.post('/api/v1/keys/create/', json.dumps({'name': 'One Too Many'}),
            content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_revoke_key(self):
        key = APIKey.objects.create(user=self.user, name='ToRevoke')
        r = self.c.post(f'/api/v1/keys/{key.pk}/revoke/')
        self.assertTrue(r.json()['ok'])
        self.assertFalse(APIKey.objects.filter(pk=key.pk).exists())

    def test_docs_page_requires_login(self):
        c2 = Client()
        r = c2.get('/api/v1/docs/')
        self.assertEqual(r.status_code, 302)


class WebhookDispatchTests(TestCase):
    """Integration test: spins up a real local HTTP server to receive the webhook."""

    def test_webhook_fires_with_valid_signature_on_scan(self):
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
            fire_event('qr.scanned', {'short_code': 'xyz'})
            time.sleep(0.5)
            self.assertEqual(len(received), 0)
        finally:
            server.shutdown()
