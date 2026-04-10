"""
tests.py — full test suite for QR Forge
Run: python manage.py test qrapp -v 2
"""
from django.test import TestCase, Client
from .models import QRCode
from .qr_utils import (generate_qr_image,
                       build_url, build_vcard, build_wifi,
                       build_sms, build_email, build_phone, build_location)


# ── qr_utils tests ─────────────────────────────────────────────────────────

class QRUtilsTests(TestCase):

    def _assert_png(self, result):
        self.assertTrue(result.startswith('data:image/png;base64,'), result[:60])

    def test_generate_square(self):
        self._assert_png(generate_qr_image('https://example.com', style='square'))

    def test_generate_rounded(self):
        self._assert_png(generate_qr_image('https://example.com', style='rounded'))

    def test_generate_custom_colors(self):
        self._assert_png(generate_qr_image('test', color='#1a1a2e', bg='#f0f0f0'))

    def test_size_min_clamp(self):
        self._assert_png(generate_qr_image('test', size=5))   # clamped to 100

    def test_size_max_clamp(self):
        self._assert_png(generate_qr_image('test', size=9999)) # clamped to 1000

    def test_build_url_adds_https(self):
        self.assertEqual(build_url('google.com'), 'https://google.com')

    def test_build_url_keeps_https(self):
        self.assertEqual(build_url('https://google.com'), 'https://google.com')

    def test_build_url_keeps_http(self):
        self.assertEqual(build_url('http://local'), 'http://local')

    def test_build_vcard(self):
        v = build_vcard({'first_name': 'John', 'last_name': 'Doe', 'email': 'j@d.com'})
        self.assertIn('BEGIN:VCARD', v)
        self.assertIn('END:VCARD', v)
        self.assertIn('John', v)
        self.assertIn('j@d.com', v)

    def test_build_wifi_wpa(self):
        self.assertEqual(build_wifi('Net', 'pass', 'WPA'), 'WIFI:T:WPA;S:Net;P:pass;;')

    def test_build_wifi_nopass(self):
        r = build_wifi('Open', '', 'nopass')
        self.assertIn('nopass', r)

    def test_build_sms(self):
        self.assertEqual(build_sms('+201', 'Hi'), 'SMSTO:+201:Hi')

    def test_build_email(self):
        r = build_email('a@b.com', 'Sub', 'Body')
        self.assertIn('MATMSG', r)
        self.assertIn('a@b.com', r)

    def test_build_phone(self):
        self.assertEqual(build_phone('+201234'), 'tel:+201234')

    def test_build_location(self):
        self.assertEqual(build_location(30.0, 31.0), 'geo:30.0,31.0')


# ── Model tests ─────────────────────────────────────────────────────────────

class ModelTests(TestCase):

    def _make(self, **kw):
        defaults = dict(qr_type='url', content='https://example.com')
        defaults.update(kw)
        return QRCode.objects.create(**defaults)

    def test_create(self):
        q = self._make(label='Test', qr_color='#111', bg_color='#fff', qr_size=400)
        self.assertEqual(q.label, 'Test')
        self.assertEqual(q.qr_color, '#111')
        self.assertEqual(q.qr_size, 400)

    def test_display_label_uses_label(self):
        q = self._make(label='My Link')
        self.assertEqual(q.display_label(), 'My Link')

    def test_display_label_falls_back_to_content(self):
        q = self._make(label='', content='https://example.com')
        self.assertIn('example.com', q.display_label())

    def test_display_label_falls_back_to_type(self):
        q = self._make(label='', content='')
        self.assertEqual(q.display_label(), 'URL')

    def test_ordering_latest_first(self):
        a = self._make(content='a')
        b = self._make(content='b')
        qs = list(QRCode.objects.all())
        self.assertEqual(qs[0].id, b.id)

    def test_str(self):
        q = self._make(label='hello')
        self.assertIn('URL', str(q))
        self.assertIn('hello', str(q))


# ── View tests ───────────────────────────────────────────────────────────────

class ViewTests(TestCase):

    def setUp(self):
        self.c = Client()

    # index
    def test_index_ok(self):
        self.assertEqual(self.c.get('/').status_code, 200)

    # generate – method guard
    def test_generate_get_405(self):
        self.assertEqual(self.c.get('/api/generate/').status_code, 405)

    # generate – all 8 types
    def _gen(self, payload):
        return self.c.post('/api/generate/', payload).json()

    def test_type_url(self):
        d = self._gen({'type': 'url', 'url': 'https://example.com'})
        self.assertTrue(d['ok'])
        self.assertTrue(d['image'].startswith('data:image/png;base64,'))

    def test_type_text(self):
        d = self._gen({'type': 'text', 'text': 'Hello world'})
        self.assertTrue(d['ok'])

    def test_type_contact(self):
        d = self._gen({'type': 'contact', 'first_name': 'A', 'last_name': 'B'})
        self.assertTrue(d['ok'])

    def test_type_wifi(self):
        d = self._gen({'type': 'wifi', 'ssid': 'Net', 'password': 'pw', 'encryption': 'WPA'})
        self.assertTrue(d['ok'])

    def test_type_wifi_nopass(self):
        d = self._gen({'type': 'wifi', 'ssid': 'Open', 'password': '', 'encryption': 'nopass'})
        self.assertTrue(d['ok'])

    def test_type_sms(self):
        d = self._gen({'type': 'sms', 'phone': '+201', 'message': 'Hi'})
        self.assertTrue(d['ok'])

    def test_type_email(self):
        d = self._gen({'type': 'email', 'email': 'a@b.com', 'subject': 'S', 'body': 'B'})
        self.assertTrue(d['ok'])

    def test_type_phone(self):
        d = self._gen({'type': 'phone', 'phone': '+201234'})
        self.assertTrue(d['ok'])

    def test_type_location(self):
        d = self._gen({'type': 'location', 'latitude': '30.0', 'longitude': '31.0'})
        self.assertTrue(d['ok'])

    # generate – validation errors
    def test_invalid_type(self):
        d = self._gen({'type': 'bad'})
        self.assertFalse(d['ok'])

    def test_empty_url(self):
        d = self._gen({'type': 'url', 'url': ''})
        self.assertFalse(d['ok'])

    def test_invalid_url(self):
        d = self._gen({'type': 'url', 'url': 'not-a-url'})
        self.assertFalse(d['ok'])

    def test_invalid_email(self):
        d = self._gen({'type': 'email', 'email': 'bad', 'subject': '', 'body': ''})
        self.assertFalse(d['ok'])

    # generate – saves to DB with image
    def test_saves_to_db(self):
        self._gen({'type': 'url', 'url': 'https://example.com', 'label': 'Test Label'})
        q = QRCode.objects.get()
        self.assertEqual(q.label, 'Test Label')
        self.assertTrue(q.image_b64.startswith('data:image/png;base64,'))

    # generate – custom options saved
    def test_custom_options_saved(self):
        self._gen({'type': 'text', 'text': 'hi',
                   'qr_color': '#ff0000', 'bg_color': '#0000ff',
                   'size': '500', 'style': 'rounded'})
        q = QRCode.objects.get()
        self.assertEqual(q.qr_color, '#ff0000')
        self.assertEqual(q.qr_size, 500)
        self.assertEqual(q.qr_style, 'rounded')

    # history
    def test_history_empty(self):
        d = self.c.get('/api/history/').json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['items'], [])

    def test_history_has_fields(self):
        self._gen({'type': 'url', 'url': 'https://example.com', 'label': 'L'})
        d = self.c.get('/api/history/').json()
        self.assertEqual(len(d['items']), 1)
        item = d['items'][0]
        for key in ('id','qr_type','type_label','label','created_at','image'):
            self.assertIn(key, item, f'Missing key: {key}')

    def test_history_get_only(self):
        self.assertEqual(self.c.post('/api/history/').status_code, 405)

    # delete
    def test_delete(self):
        self._gen({'type': 'text', 'text': 'x'})
        pk = QRCode.objects.get().pk
        d  = self.c.post(f'/api/delete/{pk}/').json()
        self.assertTrue(d['ok'])
        self.assertEqual(QRCode.objects.count(), 0)

    def test_delete_not_found(self):
        d = self.c.post('/api/delete/99999/').json()
        self.assertFalse(d['ok'])

    # clear
    def test_clear(self):
        self._gen({'type': 'text', 'text': 'a'})
        self._gen({'type': 'text', 'text': 'b'})
        self.c.post('/api/clear/')
        self.assertEqual(QRCode.objects.count(), 0)
