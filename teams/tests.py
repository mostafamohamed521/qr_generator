"""
tests.py — teams app test suite
Run: python manage.py test teams -v 2
"""
import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Team, TeamMember, TeamInvite


class TeamCreationTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('owner@example.com', 'owner@example.com', 'pass12345')
        self.c.login(username='owner@example.com', password='pass12345')

    def test_create_team_makes_creator_owner(self):
        r = self.c.post('/teams/api/create/', json.dumps({'name': 'Alpha Squad'}),
                         content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        team = Team.objects.get(pk=d['team']['id'])
        self.assertEqual(team.owner, self.user)
        self.assertTrue(TeamMember.objects.filter(team=team, user=self.user, role='owner').exists())

    def test_create_team_requires_name(self):
        r = self.c.post('/teams/api/create/', json.dumps({'name': ''}),
                         content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_slug_uniqueness(self):
        self.c.post('/teams/api/create/', json.dumps({'name': 'Design'}), content_type='application/json')
        r2 = self.c.post('/teams/api/create/', json.dumps({'name': 'Design'}), content_type='application/json')
        teams = Team.objects.filter(name='Design')
        self.assertEqual(teams.count(), 2)
        slugs = set(teams.values_list('slug', flat=True))
        self.assertEqual(len(slugs), 2)  # must be unique


class TeamMembershipTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.owner = User.objects.create_user('owner2@example.com', 'owner2@example.com', 'pass12345')
        self.member = User.objects.create_user('member@example.com', 'member@example.com', 'pass12345')
        self.c.login(username='owner2@example.com', password='pass12345')
        r = self.c.post('/teams/api/create/', json.dumps({'name': 'Beta Team'}), content_type='application/json')
        self.team_id = r.json()['team']['id']

    def test_invite_existing_user_auto_adds(self):
        r = self.c.post(f'/teams/api/{self.team_id}/invite/',
            json.dumps({'email': 'member@example.com', 'role': 'member'}),
            content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertTrue(d.get('auto_added'))
        self.assertTrue(TeamMember.objects.filter(team_id=self.team_id, user=self.member).exists())

    def test_invite_new_email_creates_pending_invite(self):
        r = self.c.post(f'/teams/api/{self.team_id}/invite/',
            json.dumps({'email': 'stranger@example.com', 'role': 'member'}),
            content_type='application/json')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertIn('invite_url', d)
        self.assertTrue(TeamInvite.objects.filter(team_id=self.team_id, email='stranger@example.com').exists())

    def test_invite_sends_email_for_new_user(self):
        from django.core import mail
        self.c.post(f'/teams/api/{self.team_id}/invite/',
            json.dumps({'email': 'newbie@example.com', 'role': 'member'}),
            content_type='application/json')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('invited', mail.outbox[0].body.lower())

    def test_non_admin_cannot_invite(self):
        TeamMember.objects.create(team_id=self.team_id, user=self.member, role='member')
        c2 = Client()
        c2.login(username='member@example.com', password='pass12345')
        r = c2.post(f'/teams/api/{self.team_id}/invite/',
            json.dumps({'email': 'x@example.com', 'role': 'member'}),
            content_type='application/json')
        self.assertEqual(r.status_code, 403)

    def test_members_list_shows_role(self):
        r = self.c.get(f'/teams/api/{self.team_id}/members/')
        d = r.json()
        self.assertTrue(d['ok'])
        self.assertEqual(d['members'][0]['role'], 'owner')

    def test_change_role(self):
        TeamMember.objects.create(team_id=self.team_id, user=self.member, role='member')
        r = self.c.post(f'/teams/api/{self.team_id}/role/{self.member.id}/',
            json.dumps({'role': 'admin'}), content_type='application/json')
        self.assertTrue(r.json()['ok'])
        m = TeamMember.objects.get(team_id=self.team_id, user=self.member)
        self.assertEqual(m.role, 'admin')

    def test_cannot_change_owner_role(self):
        r = self.c.post(f'/teams/api/{self.team_id}/role/{self.owner.id}/',
            json.dumps({'role': 'member'}), content_type='application/json')
        self.assertFalse(r.json()['ok'])

    def test_remove_member(self):
        TeamMember.objects.create(team_id=self.team_id, user=self.member, role='member')
        r = self.c.post(f'/teams/api/{self.team_id}/remove/{self.member.id}/')
        self.assertTrue(r.json()['ok'])
        self.assertFalse(TeamMember.objects.filter(team_id=self.team_id, user=self.member).exists())

    def test_owner_cannot_leave(self):
        r = self.c.post(f'/teams/api/{self.team_id}/leave/')
        self.assertFalse(r.json()['ok'])

    def test_member_can_leave(self):
        TeamMember.objects.create(team_id=self.team_id, user=self.member, role='member')
        c2 = Client()
        c2.login(username='member@example.com', password='pass12345')
        r = c2.post(f'/teams/api/{self.team_id}/leave/')
        self.assertTrue(r.json()['ok'])

    def test_switch_active_team(self):
        r = self.c.post(f'/teams/api/{self.team_id}/switch/')
        d = r.json()
        self.assertTrue(d['ok'])
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.active_team_id, self.team_id)

    def test_audit_log_records_actions(self):
        r = self.c.get(f'/teams/api/{self.team_id}/audit/')
        d = r.json()
        self.assertTrue(d['ok'])
        actions = [e['action'] for e in d['entries']]
        self.assertIn('team.created', actions)


class TeamAccessControlTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user('own3@example.com', 'own3@example.com', 'pass12345')
        self.outsider = User.objects.create_user('out@example.com', 'out@example.com', 'pass12345')
        c = Client()
        c.login(username='own3@example.com', password='pass12345')
        r = c.post('/teams/api/create/', json.dumps({'name': 'Private Team'}), content_type='application/json')
        self.team_id = r.json()['team']['id']

    def test_non_member_cannot_view_members(self):
        c2 = Client()
        c2.login(username='out@example.com', password='pass12345')
        r = c2.get(f'/teams/api/{self.team_id}/members/')
        self.assertEqual(r.status_code, 403)

    def test_teams_page_requires_login(self):
        c2 = Client()
        r = c2.get('/teams/')
        self.assertEqual(r.status_code, 302)
