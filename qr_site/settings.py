import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

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
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-qr-forge-change-this-in-production-xyz-2024')
DEBUG      = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

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
