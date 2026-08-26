import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from a .env file at the project root into os.environ, if
# one exists (a plain .env with no such loader was previously present in
# this project and did nothing — every os.environ.get() below silently
# fell back to its default regardless of what was in the file). Real
# environment variables set outside .env still take precedence.
load_dotenv(BASE_DIR / '.env')

# ── Email ─────────────────────────────────────────────────────────────────────
# Default: prints emails to the console (safe for dev, no secrets needed).
# For production, set these env vars and the backend switches to real SMTP:
#   DJANGO_EMAIL_HOST, DJANGO_EMAIL_PORT, DJANGO_EMAIL_HOST_USER,
#   DJANGO_EMAIL_HOST_PASSWORD, DJANGO_EMAIL_USE_TLS=true
EMAIL_HOST = os.environ.get('DJANGO_EMAIL_HOST', '')

if EMAIL_HOST:
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT          = int(os.environ.get('DJANGO_EMAIL_PORT', 587))
    EMAIL_HOST_USER     = os.environ.get('DJANGO_EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS       = os.environ.get('DJANGO_EMAIL_USE_TLS', 'true').lower() == 'true'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'QR Forge <noreply@qrforge.local>')
# Where contact-form submissions are emailed to (best-effort notification —
# the message itself is always saved to the database regardless). Empty by
# default so a fresh install doesn't silently fail_silently-swallow mail
# errors trying to reach an address nobody configured.
CONTACT_NOTIFY_EMAIL = os.environ.get('DJANGO_CONTACT_NOTIFY_EMAIL', '')
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # 24 hours

# ── Security ──────────────────────────────────────────────────────────────────
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'

_INSECURE_DEFAULT_KEY = 'django-insecure-qr-forge-change-this-in-production-xyz-2024'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', _INSECURE_DEFAULT_KEY)
if not DEBUG and SECRET_KEY == _INSECURE_DEFAULT_KEY:
    # Refuse to boot in production with the shipped placeholder key — this
    # key is public (it's in the repo), so leaving it in place lets anyone
    # forge session cookies, password-reset tokens, and signed data.
    raise RuntimeError(
        'DJANGO_SECRET_KEY is not set. Generate one with: '
        'python -c "from django.core.management.utils import get_random_secret_key; '
        'print(get_random_secret_key())" and set it as an environment variable '
        'before running with DJANGO_DEBUG=false.'
    )

_allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS', '').strip()
if not DEBUG and not _allowed_hosts_env:
    raise RuntimeError(
        'DJANGO_ALLOWED_HOSTS is not set. In production this must be your '
        'real domain(s), e.g. "yourdomain.com,www.yourdomain.com" — never "*".'
    )
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(',') if h.strip()] or ['*']

# Only trust X-Forwarded-For / X-Forwarded-Proto if you are actually behind a
# reverse proxy that sets them itself (nginx config in DEPLOY.md does this)
# and strips any client-supplied copy of these headers first. If this is on
# and there's no such proxy, a client can spoof its own IP/scheme and bypass
# rate limiting and HTTPS checks — leave this off unless you've verified that.
TRUST_PROXY_HEADERS = os.environ.get('DJANGO_TRUST_PROXY_HEADERS', 'false').lower() == 'true'
if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Comma-separated list of scheme+host origins allowed to POST cross-site
# (needed behind a reverse proxy / custom domain per Django 4+ CSRF rules).
_csrf_trusted = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').strip()
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_trusted.split(',') if o.strip()]

# Cap request body size to stop memory-exhaustion DoS via oversized uploads
# (profile pictures, bulk-generate payloads, etc). 5 MB is generous headroom
# above any legitimate form/image on this site.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY    = False  # JS reads this to set the X-CSRFToken header on fetch()
X_FRAME_OPTIONS         = 'DENY'
SECURE_REFERRER_POLICY  = 'same-origin'

# Production security headers (set via env when deploying)
if not DEBUG:
    SECURE_SSL_REDIRECT          = True
    SESSION_COOKIE_SECURE        = True
    CSRF_COOKIE_SECURE           = True
    SECURE_BROWSER_XSS_FILTER    = True
    SECURE_CONTENT_TYPE_NOSNIFF  = True
    SECURE_HSTS_SECONDS          = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD          = True

# ── Apps ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'qrapp',
    'core',
    'accounts',
    'teams',
    'billing',
    'api',
    'dashboard',
]

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'qr_site.middleware.RateLimitMiddleware',   # custom rate limiter
]

ROOT_URLCONF = 'qr_site.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'django.template.context_processors.i18n',
        'qr_site.context_processors.language_toggle',
    ]},
}]

WSGI_APPLICATION = 'qr_site.wsgi.application'

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': BASE_DIR / 'db.sqlite3',
}}

# ── i18n ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en'
TIME_ZONE     = 'UTC'
USE_I18N      = True
USE_TZ        = True

LANGUAGES = [
    ('en', 'English'),
    ('ar', 'العربية'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']

# ── Auth ──────────────────────────────────────────────────────────────────────
LOGIN_URL          = 'accounts:login'
LOGIN_REDIRECT_URL = 'qrapp:index'
LOGOUT_REDIRECT_URL= 'core:landing'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Static / Media ────────────────────────────────────────────────────────────
STATIC_URL      = '/static/'
STATICFILES_DIRS= [BASE_DIR / 'static']
STATIC_ROOT     = BASE_DIR / 'staticfiles'
MEDIA_URL       = '/media/'
MEDIA_ROOT      = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Rate Limiting (per IP per minute) ────────────────────────────────────────
RATE_LIMIT_GENERATE   = 30   # generate endpoint per minute
RATE_LIMIT_AUTH       = 10   # login/register per minute
RATE_LIMIT_GLOBAL     = 200  # all other API per minute

# ── Stripe ────────────────────────────────────────────────────────────────────
# Checkout is not implemented yet (see billing app). These are read so the
# webhook handler can verify signatures once real keys are configured; until
# then they're empty and the webhook fails closed (rejects everything) rather
# than trusting unverified input.
STRIPE_SECRET_KEY     = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '[%(levelname)s %(asctime)s] %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'qrapp':  {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'teams':  {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
