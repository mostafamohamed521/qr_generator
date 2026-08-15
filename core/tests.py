"""
tests.py — core app test suite (landing pages + i18n/Arabic translation)
Run: python manage.py test core -v 2

The Arabic translation tests exist specifically to prevent the site from
silently regressing back to "RTL layout with English text" — a real bug
that existed for a long time because no .po/.mo translation catalog was
ever compiled, even though {% trans %} tags were used everywhere.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User


class LandingPageTests(TestCase):

    def setUp(self):
        self.c = Client()

    def test_landing_page_loads(self):
        r = self.c.get('/')
        self.assertEqual(r.status_code, 200)

    def test_pricing_page_loads(self):
        r = self.c.get('/pricing/')
        self.assertEqual(r.status_code, 200)

    def test_about_page_loads(self):
        r = self.c.get('/about/')
        self.assertEqual(r.status_code, 200)

    def test_faq_page_loads(self):
        r = self.c.get('/faq/')
        self.assertEqual(r.status_code, 200)

    def test_contact_page_loads(self):
        r = self.c.get('/contact/')
        self.assertEqual(r.status_code, 200)

    def test_contact_submit_saves_message(self):
        """Was previously a fake success toast that never sent anything
        anywhere — found during a full page audit and given a real backend."""
        from core.models import ContactMessage
        import json
        r = self.c.post('/contact/submit/',
            json.dumps({'email': 'visitor@example.com', 'message': 'Hello there'}),
            content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(ContactMessage.objects.count(), 1)
        msg = ContactMessage.objects.get()
        self.assertEqual(msg.email, 'visitor@example.com')
        self.assertEqual(msg.message, 'Hello there')

    def test_contact_submit_rejects_invalid_email(self):
        import json
        r = self.c.post('/contact/submit/',
            json.dumps({'email': 'not-an-email', 'message': 'Hi'}),
            content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_contact_submit_rejects_empty_message(self):
        import json
        r = self.c.post('/contact/submit/',
            json.dumps({'email': 'visitor@example.com', 'message': ''}),
            content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_contact_submit_get_not_allowed(self):
        r = self.c.get('/contact/submit/')
        self.assertEqual(r.status_code, 405)

    def test_robots_txt(self):
        r = self.c.get('/robots.txt')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Disallow: /admin/', r.content)

    def test_sitemap_xml(self):
        r = self.c.get('/sitemap.xml')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'<urlset', r.content)


class ArabicTranslationTests(TestCase):
    """
    Guards against the site silently reverting to untranslated English
    content when /ar/ is requested. A missing .mo catalog makes every
    {% trans %} tag fall back to English while dir="rtl" still flips the
    layout — broken i18n that looks fine at a glance but isn't.
    """

    def setUp(self):
        self.c = Client()

    def test_arabic_landing_page_sets_rtl_direction(self):
        r = self.c.get('/ar/')
        self.assertContains(r, 'dir="rtl"')

    def test_arabic_landing_page_is_actually_translated(self):
        r = self.c.get('/ar/')
        content = r.content.decode()
        # These specific English strings must NOT survive translation
        self.assertNotIn('Get started free', content)
        self.assertNotIn('See pricing', content)
        self.assertNotIn('Everything you need', content)
        # And real Arabic text must be present
        self.assertIn('ابدأ مجانًا', content)

    def test_arabic_pricing_page_translated(self):
        r = self.c.get('/ar/pricing/')
        self.assertIn('الأسعار', r.content.decode())

    def test_arabic_login_page_translated(self):
        r = self.c.get('/ar/accounts/login/')
        self.assertIn('تسجيل الدخول', r.content.decode())

    def test_arabic_dashboard_nav_translated(self):
        User.objects.create_user('arnav@example.com', 'arnav@example.com', 'pass12345')
        self.c.login(username='arnav@example.com', password='pass12345')
        r = self.c.get('/ar/app/')
        content = r.content.decode()
        self.assertIn('التحليلات', content)   # Analytics
        self.assertIn('الفرق', content)       # Teams

    def test_english_default_still_works(self):
        """Switching translations on for Arabic must not break the English default."""
        r = self.c.get('/')
        self.assertContains(r, 'Get started free')

    def test_language_switch_form_toggles_correctly(self):
        r = self.c.post('/i18n/setlang/', {'language': 'ar', 'next': '/'}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'dir="rtl"')
