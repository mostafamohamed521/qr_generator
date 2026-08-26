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


class UserListQrCountTests(TestCase):
    """Regression test: qr_count was hardcoded to 0 everywhere in this app
    (list, CSV export, "top users") instead of actually being counted."""

    def setUp(self):
        self.c = Client()
        self.staff = User.objects.create_user('staff3@example.com', 'staff3@example.com', 'pass12345', is_staff=True)
        self.target = User.objects.create_user('hasqrs@example.com', 'hasqrs@example.com', 'pass12345')
        self.c.login(username='staff3@example.com', password='pass12345')

        from qrapp.models import QRCode
        for i in range(3):
            QRCode.objects.create(user=self.target, qr_type='text', content=f'test {i}', image_b64='')

    def test_users_list_reports_real_qr_count(self):
        r = self.c.get('/dashboard/api/users/')
        d = r.json()
        row = next(u for u in d['users'] if u['id'] == self.target.pk)
        self.assertEqual(row['qr_count'], 3)

    def test_top_users_orders_by_activity_not_signup_date(self):
        # target has 3 QR codes and joined after staff (who has 0) -- top
        # users must rank by actual QR count, not just "most recent".
        r = self.c.get('/dashboard/api/stats/')
        d = r.json()
        self.assertEqual(d['top_users'][0]['email'], 'hasqrs@example.com')
        self.assertEqual(d['top_users'][0]['qr_count'], 3)


class DeleteUserTeamCascadeGuardTests(TestCase):
    """Regression test: deleting a user via the admin dashboard who owned a
    team with other members used to silently cascade-delete that whole
    team (Team.owner is on_delete=CASCADE) -- the same class of bug that
    was already guarded against in accounts.delete_account_view, just
    missing here."""

    def setUp(self):
        self.c = Client()
        self.staff = User.objects.create_user('staff4@example.com', 'staff4@example.com', 'pass12345', is_staff=True)
        self.owner = User.objects.create_user('owner@example.com', 'owner@example.com', 'pass12345')
        self.member = User.objects.create_user('member@example.com', 'member@example.com', 'pass12345')
        self.c.login(username='staff4@example.com', password='pass12345')

        from teams.models import Team, TeamMember
        self.team = Team.objects.create(name='Squad', slug='squad', owner=self.owner)
        TeamMember.objects.create(team=self.team, user=self.owner, role='owner')
        TeamMember.objects.create(team=self.team, user=self.member, role='member')

    def test_cannot_delete_user_who_owns_team_with_other_members(self):
        from teams.models import Team
        r = self.c.post(f'/dashboard/api/users/{self.owner.pk}/delete/')
        d = r.json()
        self.assertEqual(r.status_code, 400)
        self.assertFalse(d['ok'])
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(Team.objects.filter(pk=self.team.pk).exists())

    def test_can_delete_user_whose_owned_team_has_no_other_members(self):
        from teams.models import Team, TeamMember
        solo_owner = User.objects.create_user('solo@example.com', 'solo@example.com', 'pass12345')
        solo_team = Team.objects.create(name='Solo', slug='solo', owner=solo_owner)
        TeamMember.objects.create(team=solo_team, user=solo_owner, role='owner')

        r = self.c.post(f'/dashboard/api/users/{solo_owner.pk}/delete/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertFalse(User.objects.filter(pk=solo_owner.pk).exists())
