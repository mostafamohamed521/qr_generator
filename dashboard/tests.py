"""
tests.py — dashboard app test suite
Run: python manage.py test dashboard -v 2

This app had no tests at all before this consistency sweep, even though it
received a real security fix earlier in this audit: toggle_user/delete_user
previously let any staff (is_staff=True, not necessarily superuser) account
grant staff access to other users and modify/delete other staff or
superuser accounts. Covering that fix here since it had zero verification
until now.
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User


class DashboardAccessTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.staff = User.objects.create_user('staffuser@example.com', 'staffuser@example.com', 'pass12345', is_staff=True)
        self.plain = User.objects.create_user('plainuser@example.com', 'plainuser@example.com', 'pass12345')

    def test_plain_user_cannot_access_dashboard(self):
        self.c.login(username='plainuser@example.com', password='pass12345')
        r = self.c.get('/dashboard/')
        self.assertNotEqual(r.status_code, 200)

    def test_staff_user_can_access_dashboard(self):
        self.c.login(username='staffuser@example.com', password='pass12345')
        r = self.c.get('/dashboard/')
        self.assertEqual(r.status_code, 200)

    def test_anonymous_redirected(self):
        r = self.c.get('/dashboard/')
        self.assertEqual(r.status_code, 302)


class PrivilegeEscalationFixTests(TestCase):
    """toggle_user / delete_user — the actual security fix under test here."""

    def setUp(self):
        self.c = Client()
        self.staff = User.objects.create_user('staff2@example.com', 'staff2@example.com', 'pass12345', is_staff=True)
        self.superuser = User.objects.create_superuser('super@example.com', 'super@example.com', 'pass12345')
        self.target = User.objects.create_user('target@example.com', 'target@example.com', 'pass12345')
        self.c.login(username='staff2@example.com', password='pass12345')

    def test_plain_staff_cannot_grant_is_staff(self):
        r = self.c.post(f'/dashboard/api/users/{self.target.pk}/toggle/',
            json.dumps({'is_staff': True}), content_type='application/json')
        self.assertEqual(r.status_code, 403)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_staff)

    def test_plain_staff_can_still_toggle_is_active(self):
        """The fix should only gate is_staff and superuser targets -- ordinary
        activate/deactivate of a non-superuser must keep working."""
        r = self.c.post(f'/dashboard/api/users/{self.target.pk}/toggle/',
            json.dumps({'is_active': False}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_plain_staff_cannot_modify_superuser(self):
        r = self.c.post(f'/dashboard/api/users/{self.superuser.pk}/toggle/',
            json.dumps({'is_active': False}), content_type='application/json')
        self.assertEqual(r.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_plain_staff_cannot_delete_superuser(self):
        r = self.c.post(f'/dashboard/api/users/{self.superuser.pk}/delete/')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.superuser.pk).exists())

    def test_superuser_can_grant_is_staff(self):
        c2 = Client()
        c2.login(username='super@example.com', password='pass12345')
        r = c2.post(f'/dashboard/api/users/{self.target.pk}/toggle/',
            json.dumps({'is_staff': True}), content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_staff)

    def test_superuser_can_modify_another_superuser(self):
        other_super = User.objects.create_superuser('super2@example.com', 'super2@example.com', 'pass12345')
        c2 = Client()
        c2.login(username='super@example.com', password='pass12345')
        r = c2.post(f'/dashboard/api/users/{other_super.pk}/toggle/',
            json.dumps({'is_active': False}), content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def test_cannot_modify_own_account(self):
        r = self.c.post(f'/dashboard/api/users/{self.staff.pk}/toggle/',
            json.dumps({'is_active': False}), content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_cannot_delete_own_account(self):
        r = self.c.post(f'/dashboard/api/users/{self.staff.pk}/delete/')
        self.assertEqual(r.status_code, 400)

    def test_plain_staff_can_delete_ordinary_user(self):
        r = self.c.post(f'/dashboard/api/users/{self.target.pk}/delete/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.target.pk).exists())

    def test_toggle_requires_staff(self):
        c2 = Client()
        plain = User.objects.create_user('plaintoggle@example.com', 'plaintoggle@example.com', 'pass12345')
        c2.login(username='plaintoggle@example.com', password='pass12345')
        r = c2.post(f'/dashboard/api/users/{self.target.pk}/toggle/',
            json.dumps({'is_active': False}), content_type='application/json')
        self.assertNotEqual(r.status_code, 200)
