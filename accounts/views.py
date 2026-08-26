from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse

from .forms import RegisterForm, LoginForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('qrapp:index')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)
        try:
            send_verification_email(user)
        except Exception:
            pass  # don't block registration if email sending fails (e.g. no SMTP configured)
        messages.success(request, 'Welcome to QR Forge! Your account is ready.')
        return redirect('qrapp:index')

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('qrapp:index')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data['user']

        # If 2FA is enabled, hold login until a valid TOTP code is provided
        if getattr(user, 'profile', None) and user.profile.two_factor_enabled:
            request.session['pending_2fa_user_id'] = user.pk
            request.session['pending_2fa_remember'] = bool(form.cleaned_data.get('remember'))
            return redirect('accounts:twofa_verify')

        auth_login(request, user)
        if form.cleaned_data.get('remember'):
            request.session.set_expiry(60 * 60 * 24 * 30)  # 30 days
        else:
            request.session.set_expiry(0)  # browser-session only
        next_url = request.GET.get('next') or reverse('qrapp:index')
        return redirect(next_url)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    auth_logout(request)
    return redirect('core:landing')


def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            first, _, last = name.partition(' ')
            request.user.first_name = first[:150]
            request.user.last_name = last[:150]
            request.user.save(update_fields=['first_name', 'last_name'])

        avatar = request.FILES.get('avatar')
        if avatar:
            error = _validate_avatar(avatar)
            if error:
                messages.error(request, error)
                return redirect('accounts:profile')
            profile = request.user.profile
            # remove old avatar file to avoid orphaned files piling up
            if profile.avatar:
                profile.avatar.delete(save=False)
            profile.avatar = avatar
            profile.save(update_fields=['avatar'])

        messages.success(request, 'Profile updated.')
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html')


def _validate_avatar(file):
    """Return an error string if the uploaded avatar is invalid, else None."""
    MAX_SIZE = 3 * 1024 * 1024  # 3 MB
    ALLOWED_TYPES = {'image/jpeg', 'image/png', 'image/webp'}

    if file.size > MAX_SIZE:
        return 'Avatar must be under 3 MB.'
    if file.content_type not in ALLOWED_TYPES:
        return 'Avatar must be a JPEG, PNG, or WebP image.'

    try:
        from PIL import Image
        img = Image.open(file)
        img.verify()  # raises if not a valid image (defends against renamed non-image files)
        file.seek(0)
    except Exception:
        return 'That file doesn\'t look like a valid image.'

    return None


def remove_avatar_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.method == 'POST':
        profile = request.user.profile
        if profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=['avatar'])
        messages.success(request, 'Avatar removed.')
    return redirect('accounts:profile')


# ── Sprint: Password Reset & Email Verification ───────────────────────────────
import secrets
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import EmailVerificationToken


def _send_templated_email(subject, template_name, context, to_email):
    """Render a plain-text email template and send it via the configured backend."""
    body = render_to_string(template_name, context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[to_email],
        fail_silently=False,
    )


# ── Forgot password ────────────────────────────────────────────────────────────
def forgot_password_view(request):
    sent = False
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        user  = User.objects.filter(email__iexact=email).first()
        if user:
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = request.build_absolute_uri(
                reverse('accounts:reset_password', kwargs={'uidb64': uid, 'token': token})
            )
            _send_templated_email(
                subject='Reset your QR Forge password',
                template_name='accounts/email/password_reset.txt',
                context={'user': user, 'reset_url': reset_url},
                to_email=user.email,
            )
        # Always show success (don't leak whether the email exists)
        sent = True
    return render(request, 'accounts/forgot_password.html', {'sent': sent})


def reset_password_view(request, uidb64, token):
    try:
        uid  = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid = user is not None and default_token_generator.check_token(user, token)

    if not valid:
        return render(request, 'accounts/reset_password.html', {'invalid': True})

    error = None
    if request.method == 'POST':
        pw1 = request.POST.get('password1', '')
        pw2 = request.POST.get('password2', '')
        if pw1 != pw2:
            error = "Passwords don't match."
        else:
            try:
                validate_password(pw1, user=user)
            except ValidationError as e:
                error = ' '.join(e.messages)
            else:
                user.set_password(pw1)
                user.save()
                messages.success(request, 'Password reset! You can now log in.')
                return redirect('accounts:login')

    return render(request, 'accounts/reset_password.html', {'invalid': False, 'error': error})


# ── Email verification ────────────────────────────────────────────────────────
def send_verification_email(user):
    token = secrets.token_urlsafe(32)
    EmailVerificationToken.objects.filter(user=user, used=False).update(used=True)  # invalidate old
    EmailVerificationToken.objects.create(user=user, token=token)
    verify_url = f'/accounts/verify-email/{token}/'
    _send_templated_email(
        subject='Verify your QR Forge email',
        template_name='accounts/email/verify_email.txt',
        context={'user': user, 'verify_url': verify_url},
        to_email=user.email,
    )


def verify_email_view(request, token):
    try:
        vt = EmailVerificationToken.objects.get(token=token, used=False)
    except EmailVerificationToken.DoesNotExist:
        return render(request, 'accounts/verify_email.html', {'success': False})

    vt.used = True
    vt.save()
    from .models import Profile
    Profile.objects.filter(user=vt.user).update(is_email_verified=True)
    return render(request, 'accounts/verify_email.html', {'success': True})


from django.views.decorators.http import require_POST


@require_POST
def resend_verification_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    send_verification_email(request.user)
    messages.success(request, 'Verification email sent — check your inbox.')
    return redirect('accounts:profile')


# ── Two-Factor Authentication (TOTP) ──────────────────────────────────────────
from .twofa import generate_secret, generate_setup_qr, verify_code
from .models import Profile


def twofa_setup_view(request):
    """Step 1: show QR code to scan with an authenticator app."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    profile = request.user.profile
    if profile.two_factor_enabled:
        messages.info(request, '2FA is already enabled.')
        return redirect('accounts:profile')

    # Generate a fresh secret each time setup page loads (stored temporarily in session)
    secret = request.session.get('pending_2fa_secret')
    if not secret:
        secret = generate_secret()
        request.session['pending_2fa_secret'] = secret

    qr_image = generate_setup_qr(secret, request.user.email)

    error = None
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if verify_code(secret, code):
            profile.two_factor_secret  = secret
            profile.two_factor_enabled = True
            profile.save(update_fields=['two_factor_secret', 'two_factor_enabled'])
            del request.session['pending_2fa_secret']
            messages.success(request, '2FA enabled! Your account is now more secure.')
            return redirect('accounts:profile')
        error = 'Invalid code — please check your authenticator app and try again.'

    return render(request, 'accounts/twofa_setup.html', {
        'qr_image': qr_image, 'secret': secret, 'error': error,
    })


def twofa_disable_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    if request.method == 'POST':
        profile = request.user.profile
        profile.two_factor_enabled = False
        profile.two_factor_secret  = ''
        profile.save(update_fields=['two_factor_enabled', 'two_factor_secret'])
        messages.success(request, '2FA has been disabled.')
        return redirect('accounts:profile')
    return render(request, 'accounts/twofa_disable.html')


def twofa_verify_view(request):
    """
    Step 2 of login: if the user's account has 2FA enabled, LoginForm redirects
    here instead of logging them in directly. The user id is held in session
    until a valid code is submitted.
    """
    pending_user_id = request.session.get('pending_2fa_user_id')
    if not pending_user_id:
        return redirect('accounts:login')

    error = None
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        try:
            user = User.objects.get(pk=pending_user_id)
            profile = user.profile
        except (User.DoesNotExist, Profile.DoesNotExist):
            return redirect('accounts:login')

        if verify_code(profile.two_factor_secret, code):
            remember = request.session.pop('pending_2fa_remember', False)
            del request.session['pending_2fa_user_id']
            auth_login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)
            return redirect('qrapp:index')
        error = 'Invalid code. Please try again.'

    return render(request, 'accounts/twofa_verify.html', {'error': error})


# ── Account deletion (self-service, GDPR-style) ───────────────────────────────
def delete_account_view(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')

    from teams.models import Team
    # Safety guard: don't silently orphan teammates by cascade-deleting a
    # shared team just because the owner deleted their personal account.
    owned_teams_with_others = [
        t for t in Team.objects.filter(owner=request.user)
        if t.members.exclude(user=request.user).exists()
    ]

    error = None
    if request.method == 'POST':
        if owned_teams_with_others:
            error = (
                'You own team(s) with other members: '
                + ', '.join(t.name for t in owned_teams_with_others)
                + '. Transfer ownership or remove those teams before deleting your account.'
            )
        else:
            password = request.POST.get('password', '')
            if not request.user.check_password(password):
                error = 'Incorrect password.'
            else:
                email = request.user.email
                user_to_delete = request.user
                auth_logout(request)
                user_to_delete.delete()  # cascades: profile, api keys, webhooks, subscription, solo teams
                messages.success(request, 'Your account has been permanently deleted.')
                return redirect('core:landing')

    return render(request, 'accounts/delete_account.html', {
        'error': error,
        'blocking_teams': owned_teams_with_others,
    })
