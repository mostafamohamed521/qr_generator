"""
tests.py — full test suite for QR Forge
Run: python manage.py test qrapp -v 2

NOTE: ViewTests/DynamicQRTests/HistorySearchTests originally used an
anonymous (unauthenticated) Client() against every endpoint here. That was
correct when this file was written, but every one of these endpoints
(generate, history, delete, clear, dynamic/*, export-csv) has required a
logged-in user and per-user ownership scoping since the qrapp ownership/
IDOR pilot — the very first phase of this audit. This file was never
updated at the time, so it's been silently failing since then. Fixed below
by logging a user in for every test that hits an authenticated endpoint;
the two dynamic_redirect tests are correctly left anonymous, since that
endpoint is meant to be public (anyone scanning the code, not just its
owner, needs to be redirected).
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import QRCode, DynamicLink
from .qr_utils import (generate_qr_image,
                       build_url, build_vcard, build_wifi,
                       build_sms, build_email, build_phone, build_location)


# ── qr_utils tests ─────────────────────────────────────────────────────────
# Pure functions, no auth/DB involved — unaffected by any of this, unchanged.

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

    def setUp(self):
        self.user = User.objects.create_user('modeltest@example.com', 'modeltest@example.com', 'pass12345')

    def _make(self, **kw):
        defaults = dict(user=self.user, qr_type='url', content='https://example.com')
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
        self.user = User.objects.create_user('viewtest@example.com', 'viewtest@example.com', 'pass12345')
        self.c.login(username='viewtest@example.com', password='pass12345')

    # index
    def test_index_ok(self):
        self.assertEqual(self.c.get('/app/').status_code, 200)

    def test_index_requires_login(self):
        c2 = Client()
        r = c2.get('/app/')
        self.assertEqual(r.status_code, 302)

    # generate – method guard
    def test_generate_get_405(self):
        self.assertEqual(self.c.get('/app/api/generate/').status_code, 405)

    def test_generate_requires_login(self):
        c2 = Client()
        r = c2.post('/app/api/generate/', {'type': 'url', 'url': 'https://example.com'})
        self.assertEqual(r.status_code, 401)  # json_login_required -> 401, not a redirect

    # generate – all 8 types
    def _gen(self, payload):
        return self.c.post('/app/api/generate/', payload).json()

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

    # generate – saves to DB with image, owned by the requesting user
    def test_saves_to_db(self):
        self._gen({'type': 'url', 'url': 'https://example.com', 'label': 'Test Label'})
        q = QRCode.objects.get()
        self.assertEqual(q.label, 'Test Label')
        self.assertEqual(q.user, self.user)
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
        d = self.c.get('/app/api/history/').json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['items'], [])

    def test_history_has_fields(self):
        self._gen({'type': 'url', 'url': 'https://example.com', 'label': 'L'})
        d = self.c.get('/app/api/history/').json()
        self.assertEqual(len(d['items']), 1)
        item = d['items'][0]
        for key in ('id','qr_type','type_label','label','created_at','image'):
            self.assertIn(key, item, f'Missing key: {key}')

    def test_history_get_only(self):
        self.assertEqual(self.c.post('/app/api/history/').status_code, 405)

    def test_history_only_shows_own_codes(self):
        """IDOR check: history must not leak another user's QR codes."""
        other = User.objects.create_user('otherviewer@example.com', 'otherviewer@example.com', 'pass12345')
        QRCode.objects.create(user=other, qr_type='text', content='not yours')
        d = self.c.get('/app/api/history/').json()
        self.assertEqual(d['items'], [])

    # delete
    def test_delete(self):
        self._gen({'type': 'text', 'text': 'x'})
        pk = QRCode.objects.get().pk
        d  = self.c.post(f'/app/api/delete/{pk}/').json()
        self.assertTrue(d['ok'])
        self.assertEqual(QRCode.objects.count(), 0)

    def test_delete_not_found(self):
        d = self.c.post('/app/api/delete/99999/').json()
        self.assertFalse(d['ok'])

    def test_cannot_delete_another_users_qrcode(self):
        other = User.objects.create_user('otherdeleter@example.com', 'otherdeleter@example.com', 'pass12345')
        q = QRCode.objects.create(user=other, qr_type='text', content='not yours')
        d = self.c.post(f'/app/api/delete/{q.pk}/').json()
        self.assertFalse(d['ok'])
        self.assertTrue(QRCode.objects.filter(pk=q.pk).exists())

    # clear
    def test_clear(self):
        self._gen({'type': 'text', 'text': 'a'})
        self._gen({'type': 'text', 'text': 'b'})
        self.c.post('/app/api/clear/')
        self.assertEqual(QRCode.objects.count(), 0)

    def test_clear_only_clears_own_codes(self):
        other = User.objects.create_user('otherclearer@example.com', 'otherclearer@example.com', 'pass12345')
        QRCode.objects.create(user=other, qr_type='text', content='not yours')
        self._gen({'type': 'text', 'text': 'mine'})
        self.c.post('/app/api/clear/')
        self.assertEqual(QRCode.objects.filter(user=self.user).count(), 0)
        self.assertEqual(QRCode.objects.filter(user=other).count(), 1)  # untouched


# ── Quota enforcement ─────────────────────────────────────────────────────────

class QuotaTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('quotaview@example.com', 'quotaview@example.com', 'pass12345')
        self.c.login(username='quotaview@example.com', password='pass12345')
        from billing.models import Plan, Subscription
        self.plan = Plan.objects.get(code='free')
        self.sub = Subscription.objects.create(user=self.user, plan=self.plan, status='active')

    def test_blocked_once_at_limit(self):
        self.plan.max_qr_per_month = 2
        self.plan.save()
        for _ in range(2):
            d = self.c.post('/app/api/generate/', {'type': 'text', 'text': 'x'}).json()
            self.assertTrue(d['ok'])
        r = self.c.post('/app/api/generate/', {'type': 'text', 'text': 'x'})
        d = r.json()
        self.assertFalse(d['ok'])
        self.assertEqual(d['code'], 'quota_exceeded')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(QRCode.objects.filter(user=self.user).count(), 2)

    def test_bulk_rejects_whole_batch_when_over_remaining(self):
        """limit=100, used=95, bulk request=10 -> reject all 10, create none."""
        self.plan.max_qr_per_month = 100
        self.plan.save()
        QRCode.objects.bulk_create([
            QRCode(user=self.user, qr_type='text', content=f'existing {i}') for i in range(95)
        ])
        items = [{'content': f'new {i}'} for i in range(10)]
        import json as jsonlib
        r = self.c.post('/app/api/bulk/', jsonlib.dumps({'items': items}), content_type='application/json')
        d = r.json()
        self.assertFalse(d['ok'])
        self.assertEqual(d['code'], 'quota_exceeded')
        self.assertEqual(QRCode.objects.filter(user=self.user).count(), 95)  # nothing added


# ── Dynamic QR tests ────────────────────────────────────────────────────────

class DynamicQRTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('dyntest@example.com', 'dyntest@example.com', 'pass12345')
        self.c.login(username='dyntest@example.com', password='pass12345')

    def test_create_dynamic_link(self):
        d = self.c.post('/app/api/dynamic/create/',
            data='{"target_url": "https://example.com", "label": "Test"}',
            content_type='application/json').json()
        self.assertTrue(d['ok'])
        self.assertIn('short_code', d['link'])
        self.assertTrue(d['link']['redirect_url'].endswith(d['link']['short_code'] + '/'))

    def test_create_rejects_invalid_url(self):
        d = self.c.post('/app/api/dynamic/create/',
            data='{"target_url": "not-a-url"}', content_type='application/json').json()
        self.assertFalse(d['ok'])

    def test_create_requires_login(self):
        c2 = Client()
        r = c2.post('/app/api/dynamic/create/',
            data='{"target_url": "https://example.com"}', content_type='application/json')
        self.assertEqual(r.status_code, 401)

    # dynamic_redirect is deliberately public — anyone scanning the code
    # needs to be redirected, not just the link's owner. Correctly
    # unauthenticated, unlike everything else in this file.
    def test_redirect_increments_scan_count(self):
        link = DynamicLink.objects.create(user=self.user, target_url='https://example.com')
        self.assertEqual(link.scan_count, 0)
        anon = Client()
        r = anon.get(f'/r/{link.short_code}/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, 'https://example.com')
        link.refresh_from_db()
        self.assertEqual(link.scan_count, 1)

    def test_redirect_inactive_link_404s(self):
        link = DynamicLink.objects.create(user=self.user, target_url='https://example.com', is_active=False)
        anon = Client()
        r = anon.get(f'/r/{link.short_code}/')
        self.assertEqual(r.status_code, 404)

    def test_redirect_unknown_code_404s(self):
        anon = Client()
        r = anon.get('/r/doesnotexist/')
        self.assertEqual(r.status_code, 404)

    def test_update_changes_target(self):
        link = DynamicLink.objects.create(user=self.user, target_url='https://old.com')
        d = self.c.post(f'/app/api/dynamic/{link.pk}/update/',
            data='{"target_url": "https://new.com"}', content_type='application/json').json()
        self.assertTrue(d['ok'])
        link.refresh_from_db()
        self.assertEqual(link.target_url, 'https://new.com')

    def test_cannot_update_another_users_link(self):
        other = User.objects.create_user('otherdynupdate@example.com', 'otherdynupdate@example.com', 'pass12345')
        link = DynamicLink.objects.create(user=other, target_url='https://old.com')
        d = self.c.post(f'/app/api/dynamic/{link.pk}/update/',
            data='{"target_url": "https://hijacked.com"}', content_type='application/json').json()
        self.assertFalse(d['ok'])
        link.refresh_from_db()
        self.assertEqual(link.target_url, 'https://old.com')

    def test_delete_link(self):
        link = DynamicLink.objects.create(user=self.user, target_url='https://example.com')
        d = self.c.post(f'/app/api/dynamic/{link.pk}/delete/').json()
        self.assertTrue(d['ok'])
        self.assertEqual(DynamicLink.objects.count(), 0)

    def test_list_links(self):
        DynamicLink.objects.create(user=self.user, target_url='https://a.com')
        DynamicLink.objects.create(user=self.user, target_url='https://b.com')
        d = self.c.get('/app/api/dynamic/').json()
        self.assertTrue(d['ok'])
        self.assertEqual(len(d['links']), 2)

    def test_list_only_shows_own_links(self):
        other = User.objects.create_user('otherdynlist@example.com', 'otherdynlist@example.com', 'pass12345')
        DynamicLink.objects.create(user=other, target_url='https://not-yours.com')
        d = self.c.get('/app/api/dynamic/').json()
        self.assertEqual(len(d['links']), 0)


# ── History search/filter/pagination ────────────────────────────────

class HistorySearchTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('histsearch@example.com', 'histsearch@example.com', 'pass12345')
        self.c.login(username='histsearch@example.com', password='pass12345')
        QRCode.objects.create(user=self.user, qr_type='url', label='Google', content='https://google.com')
        QRCode.objects.create(user=self.user, qr_type='text', label='Hello', content='Hello world')

    def test_search_by_label(self):
        d = self.c.get('/app/api/history/?q=Google').json()
        self.assertEqual(d['total'], 1)

    def test_filter_by_type(self):
        d = self.c.get('/app/api/history/?type=text').json()
        self.assertEqual(d['total'], 1)
        self.assertEqual(d['items'][0]['qr_type'], 'text')

    def test_pagination_page_size(self):
        for i in range(15):
            QRCode.objects.create(user=self.user, qr_type='text', content=f'item {i}')
        d = self.c.get('/app/api/history/?page=1').json()
        self.assertEqual(len(d['items']), 12)  # per_page = 12
        self.assertGreaterEqual(d['pages'], 2)

    def test_csv_export(self):
        r = self.c.get('/app/api/export-csv/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])

    def test_csv_export_requires_login(self):
        c2 = Client()
        r = c2.get('/app/api/export-csv/')
        self.assertEqual(r.status_code, 302)  # export_csv uses @login_required (page-style), not json_login_required
