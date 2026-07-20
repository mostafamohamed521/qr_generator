"""
tests.py — accounts app test suite (auth, password reset, email verification, 2FA)
Run: python manage.py test accounts -v 2
"""
import re
import pyotp
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Profile, EmailVerificationToken


class RegistrationTests(TestCase):

    def setUp(self):
        self.c = Client()

    def test_register_creates_user_and_logs_in(self):
        r = self.c.post('/accounts/register/', {
            'name': 'Jane Doe', 'email': 'jane@example.com', 'password': 'StrongPass123!',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(email='jane@example.com').exists())

    def test_register_auto_creates_profile(self):
        self.c.post('/accounts/register/', {
            'name': 'Jane Doe', 'email': 'jane2@example.com', 'password': 'StrongPass123!',
        })
        user = User.objects.get(email='jane2@example.com')
        self.assertTrue(hasattr(user, 'profile'))

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user('dup@example.com', 'dup@example.com', 'pass12345')
        r = self.c.post('/accounts/register/', {
            'name': 'Dup', 'email': 'dup@example.com', 'password': 'AnotherPass123!',
        })
        self.assertEqual(r.status_code, 200)  # re-renders form with error
        self.assertContains(r, 'already exists')

    def test_register_rejects_weak_password(self):
        r = self.c.post('/accounts/register/', {
            'name': 'Weak', 'email': 'weak@example.com', 'password': '123',
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.filter(email='weak@example.com').count(), 0)

    def test_register_sends_verification_email(self):
        from django.core import mail
        self.c.post('/accounts/register/', {
            'name': 'Verify Me', 'email': 'verify@example.com', 'password': 'StrongPass123!',
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Verify', mail.outbox[0].subject)


class LoginTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('login@example.com', 'login@example.com', 'CorrectPass123!')

    def test_login_success(self):
        r = self.c.post('/accounts/login/', {'email': 'login@example.com', 'password': 'CorrectPass123!'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, '/app/')

    def test_login_wrong_password(self):
        r = self.c.post('/accounts/login/', {'email': 'login@example.com', 'password': 'WrongPass'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incorrect email or password')

    def test_login_nonexistent_user(self):
        r = self.c.post('/accounts/login/', {'email': 'nope@example.com', 'password': 'whatever'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Incorrect email or password')

    def test_logout_redirects_to_landing(self):
        self.c.login(username='login@example.com', password='CorrectPass123!')
        r = self.c.get('/accounts/logout/')
        self.assertEqual(r.status_code, 302)

    def test_authenticated_user_redirected_from_login_page(self):
        self.c.login(username='login@example.com', password='CorrectPass123!')
        r = self.c.get('/accounts/login/')
        self.assertEqual(r.status_code, 302)


class PasswordResetTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('reset@example.com', 'reset@example.com', 'OldPass123!')

    def test_forgot_password_sends_email(self):
        from django.core import mail
        r = self.c.post('/accounts/forgot-password/', {'email': 'reset@example.com'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('reset-password', mail.outbox[0].body)

    def test_forgot_password_unknown_email_doesnt_leak(self):
        """Should not error or reveal whether the email exists."""
        from django.core import mail
        r = self.c.post('/accounts/forgot-password/', {'email': 'unknown@example.com'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)  # no user = no email, but response looks the same

    def test_reset_link_changes_password(self):
        from django.core import mail
        self.c.post('/accounts/forgot-password/', {'email': 'reset@example.com'})
        body = mail.outbox[0].body
        m = re.search(r'/accounts/reset-password/([^/]+)/([^/\s]+)/', body)
        uid, token = m.group(1), m.group(2)

        r = self.c.post(f'/accounts/reset-password/{uid}/{token}/', {
            'password1': 'BrandNewPass456!', 'password2': 'BrandNewPass456!',
        })
        self.assertEqual(r.status_code, 302)

        # old password should no longer work
        c2 = Client()
        self.assertFalse(c2.login(username='reset@example.com', password='OldPass123!'))
        self.assertTrue(c2.login(username='reset@example.com', password='BrandNewPass456!'))

    def test_reset_rejects_mismatched_passwords(self):
        from django.core import mail
        self.c.post('/accounts/forgot-password/', {'email': 'reset@example.com'})
        body = mail.outbox[0].body
        m = re.search(r'/accounts/reset-password/([^/]+)/([^/\s]+)/', body)
        uid, token = m.group(1), m.group(2)

        r = self.c.post(f'/accounts/reset-password/{uid}/{token}/', {
            'password1': 'Pass123456!', 'password2': 'Different123!',
        })
        self.assertContains(r, 'match')
        self.assertContains(r, 'Passwords')

    def test_invalid_reset_token_shows_error(self):
        r = self.c.get('/accounts/reset-password/bad-uid/bad-token/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'expired')


class EmailVerificationTests(TestCase):

    def setUp(self):
        self.c = Client()

    def test_valid_token_verifies_email(self):
        self.c.post('/accounts/register/', {
            'name': 'Verify Flow', 'email': 'verifyflow@example.com', 'password': 'StrongPass123!',
        })
        user = User.objects.get(email='verifyflow@example.com')
        token_obj = EmailVerificationToken.objects.filter(user=user).latest('created_at')

        r = self.c.get(f'/accounts/verify-email/{token_obj.token}/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'verified')

        user.profile.refresh_from_db()
        self.assertTrue(user.profile.is_email_verified)

    def test_invalid_token_shows_failure(self):
        r = self.c.get('/accounts/verify-email/not-a-real-token/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'invalid')

    def test_token_cannot_be_reused(self):
        self.c.post('/accounts/register/', {
            'name': 'Once', 'email': 'once@example.com', 'password': 'StrongPass123!',
        })
        user = User.objects.get(email='once@example.com')
        token_obj = EmailVerificationToken.objects.filter(user=user).latest('created_at')

        self.c.get(f'/accounts/verify-email/{token_obj.token}/')
        r2 = self.c.get(f'/accounts/verify-email/{token_obj.token}/')
        self.assertContains(r2, 'invalid')


class TwoFactorAuthTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('2fa@example.com', '2fa@example.com', 'Pass123456!')

    def _get_setup_secret(self):
        r = self.c.get('/accounts/2fa/setup/')
        m = re.search(rb'<code[^>]*>([A-Z0-9]+)</code>', r.content)
        return m.group(1).decode()

    def test_setup_requires_login(self):
        c2 = Client()
        r = c2.get('/accounts/2fa/setup/')
        self.assertEqual(r.status_code, 302)

    def test_setup_rejects_wrong_code(self):
        self.c.login(username='2fa@example.com', password='Pass123456!')
        self._get_setup_secret()
        r = self.c.post('/accounts/2fa/setup/', {'code': '000000'})
        self.assertContains(r, 'Invalid code')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.two_factor_enabled)

    def test_setup_enables_with_correct_code(self):
        self.c.login(username='2fa@example.com', password='Pass123456!')
        secret = self._get_setup_secret()
        code = pyotp.TOTP(secret).now()
        r = self.c.post('/accounts/2fa/setup/', {'code': code})
        self.assertEqual(r.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.two_factor_enabled)

    def test_login_requires_2fa_code_once_enabled(self):
        self.user.profile.two_factor_enabled = True
        self.user.profile.two_factor_secret = pyotp.random_base32()
        self.user.profile.save()

        c2 = Client()
        r = c2.post('/accounts/login/', {'email': '2fa@example.com', 'password': 'Pass123456!'})
        self.assertRedirects(r, '/accounts/2fa/verify/')

    def test_2fa_verify_wrong_code_rejected(self):
        secret = pyotp.random_base32()
        self.user.profile.two_factor_enabled = True
        self.user.profile.two_factor_secret = secret
        self.user.profile.save()

        c2 = Client()
        c2.post('/accounts/login/', {'email': '2fa@example.com', 'password': 'Pass123456!'})
        r = c2.post('/accounts/2fa/verify/', {'code': '000000'})
        self.assertContains(r, 'Invalid code')

    def test_2fa_verify_correct_code_logs_in(self):
        secret = pyotp.random_base32()
        self.user.profile.two_factor_enabled = True
        self.user.profile.two_factor_secret = secret
        self.user.profile.save()

        c2 = Client()
        c2.post('/accounts/login/', {'email': '2fa@example.com', 'password': 'Pass123456!'})
        code = pyotp.TOTP(secret).now()
        r = c2.post('/accounts/2fa/verify/', {'code': code})
        self.assertEqual(r.status_code, 302)

        profile_r = c2.get('/accounts/profile/')
        self.assertEqual(profile_r.status_code, 200)

    def test_disable_2fa(self):
        self.user.profile.two_factor_enabled = True
        self.user.profile.two_factor_secret = pyotp.random_base32()
        self.user.profile.save()

        self.c.login(username='2fa@example.com', password='Pass123456!')
        # log in bypasses 2FA in test client via force login; simulate disable directly
        r = self.c.post('/accounts/2fa/disable/')
        self.assertEqual(r.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.two_factor_enabled)
        self.assertEqual(self.user.profile.two_factor_secret, '')


# ── Profile editing & avatar upload ────────────────────────────────────────────
import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
import tempfile


def _make_test_image(fmt='PNG', size=(50, 50)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', size, color='red').save(buf, format=fmt)
    buf.seek(0)
    return buf.read()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProfileEditTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('profile@example.com', 'profile@example.com', 'pass12345',
                                              first_name='Old', last_name='Name')
        self.c.login(username='profile@example.com', password='pass12345')

    def test_update_name(self):
        r = self.c.post('/accounts/profile/', {'name': 'New Full Name'})
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'New')
        self.assertEqual(self.user.last_name, 'Full Name')

    def test_upload_valid_avatar(self):
        img_data = _make_test_image()
        avatar = SimpleUploadedFile('avatar.png', img_data, content_type='image/png')
        r = self.c.post('/accounts/profile/', {'name': 'Old Name', 'avatar': avatar})
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile.avatar))

    def test_reject_oversized_avatar(self):
        big_data = b'\x00' * (4 * 1024 * 1024)  # 4MB, over the 3MB limit
        avatar = SimpleUploadedFile('big.png', big_data, content_type='image/png')
        r = self.c.post('/accounts/profile/', {'name': 'Old Name', 'avatar': avatar}, follow=True)
        self.assertContains(r, 'under 3')
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile.avatar))

    def test_reject_non_image_file_disguised_as_image(self):
        fake = SimpleUploadedFile('fake.png', b'not actually an image', content_type='image/png')
        r = self.c.post('/accounts/profile/', {'name': 'Old Name', 'avatar': fake}, follow=True)
        self.assertContains(r, 'valid image')
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile.avatar))

    def test_reject_disallowed_content_type(self):
        fake = SimpleUploadedFile('file.gif', _make_test_image('GIF'), content_type='image/gif')
        r = self.c.post('/accounts/profile/', {'name': 'Old Name', 'avatar': fake}, follow=True)
        self.assertContains(r, 'JPEG, PNG, or WebP')

    def test_remove_avatar(self):
        img_data = _make_test_image()
        avatar = SimpleUploadedFile('avatar.png', img_data, content_type='image/png')
        self.c.post('/accounts/profile/', {'name': 'Old Name', 'avatar': avatar})
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile.avatar))

        r = self.c.post('/accounts/profile/remove-avatar/')
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(bool(self.user.profile.avatar))

    def test_profile_requires_login(self):
        c2 = Client()
        r = c2.get('/accounts/profile/')
        self.assertEqual(r.status_code, 302)


# ── Account deletion (self-service) ───────────────────────────────────────────
from teams.models import Team, TeamMember


class AccountDeletionTests(TestCase):

    def setUp(self):
        self.c = Client()
        self.user = User.objects.create_user('delete@example.com', 'delete@example.com', 'MyPass123!')
        self.c.login(username='delete@example.com', password='MyPass123!')

    def test_requires_login(self):
        c2 = Client()
        r = c2.get('/accounts/profile/delete/')
        self.assertEqual(r.status_code, 302)

    def test_wrong_password_rejected(self):
        r = self.c.post('/accounts/profile/delete/', {'password': 'WrongPassword'})
        self.assertContains(r, 'Incorrect password')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_correct_password_deletes_account(self):
        r = self.c.post('/accounts/profile/delete/', {'password': 'MyPass123!'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_deletion_logs_out_user(self):
        self.c.post('/accounts/profile/delete/', {'password': 'MyPass123!'})
        # session should be anonymous now — accessing profile redirects to login
        r = self.c.get('/accounts/profile/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r.url)

    def test_cascades_delete_api_keys(self):
        from api.models import APIKey
        APIKey.objects.create(user=self.user, name='Key')
        self.c.post('/accounts/profile/delete/', {'password': 'MyPass123!'})
        self.assertEqual(APIKey.objects.count(), 0)

    def test_solo_owned_team_deleted_with_account(self):
        Team.objects.create(name='Solo Team', slug='solo-team', owner=self.user)
        TeamMember.objects.create(team=Team.objects.get(slug='solo-team'), user=self.user, role='owner')
        r = self.c.post('/accounts/profile/delete/', {'password': 'MyPass123!'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Team.objects.filter(slug='solo-team').exists())

    def test_shared_team_blocks_deletion(self):
        """Owner shouldn't be able to accidentally nuke a team other people are in."""
        other = User.objects.create_user('teammate@example.com', 'teammate@example.com', 'pass12345')
        team = Team.objects.create(name='Shared Team', slug='shared-team', owner=self.user)
        TeamMember.objects.create(team=team, user=self.user, role='owner')
        TeamMember.objects.create(team=team, user=other, role='member')

        r = self.c.post('/accounts/profile/delete/', {'password': 'MyPass123!'})
        self.assertEqual(r.status_code, 200)  # blocked, re-renders page
        self.assertContains(r, 'Shared Team')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Team.objects.filter(slug='shared-team').exists())

    def test_after_removing_teammates_deletion_succeeds(self):
        other = User.objects.create_user('teammate2@example.com', 'teammate2@example.com', 'pass12345')
        team = Team.objects.create(name='Shared Team 2', slug='shared-team-2', owner=self.user)
        TeamMember.objects.create(team=team, user=self.user, role='owner')
        member = TeamMember.objects.create(team=team, user=other, role='member')

        # remove the other member first
        member.delete()

        r = self.c.post('/accounts/profile/delete/', {'password': 'MyPass123!'})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
