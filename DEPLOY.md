# QR Forge — Deployment Guide

## Running the test suite

Before every deploy, run the full automated test suite:

```bash
python manage.py test
```

128 tests cover authentication, password reset, email verification, 2FA,
QR generation (all 8 types), Dynamic QR + redirects, webhooks (real HTTP
delivery + HMAC signature verification), teams/permissions, billing plans,
and the public REST API. All should pass (`OK`) — if anything fails, do not
deploy until it's fixed.

Run a single app's tests during development:
```bash
python manage.py test accounts -v 2   # auth, 2FA, password reset, email
python manage.py test qrapp -v 2      # generator, history, dynamic QR
python manage.py test teams -v 2      # teams, invites, roles, audit log
python manage.py test billing -v 2    # plans, upgrade/downgrade
python manage.py test api -v 2        # REST API, webhooks
```

## Environment Variables

```bash
DJANGO_SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Email (optional — defaults to console backend if unset, which just logs emails)
DJANGO_EMAIL_HOST=smtp.sendgrid.net
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=apikey
DJANGO_EMAIL_HOST_PASSWORD=<your-provider-api-key>
DJANGO_EMAIL_USE_TLS=true
DJANGO_DEFAULT_FROM_EMAIL="QR Forge <noreply@yourdomain.com>"
```

Once `DJANGO_EMAIL_HOST` is set, password reset, email verification, and team invite
emails switch from the console backend to real SMTP automatically — no code changes needed.
Works with any SMTP provider (SendGrid, Mailgun, Amazon SES, Postmark, Gmail SMTP, etc).

## Production Setup (Ubuntu/Debian)

System dependency required for Arabic translations: `sudo apt-get install gettext`

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install gunicorn whitenoise

# 2. Collect static files
python manage.py collectstatic --noinput

# 2b. Compile translation catalogs (Arabic UI won't show translated text without this)
python manage.py compilemessages

# 3. Run migrations
python manage.py migrate

# 4. Create superuser
python manage.py createsuperuser

# 5. Start with Gunicorn
gunicorn qr_site.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 60
```

## Nginx Config (snippet)

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    location /static/ {
        alias /path/to/qr/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /path/to/qr/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Production requirements.txt additions

```
gunicorn>=21.0
whitenoise>=6.6
psycopg2-binary>=2.9   # if using PostgreSQL
```

## Database (Optional: switch to PostgreSQL)

```bash
DATABASES = {
    'default': dj_database_url.config(
        default='postgresql://user:pass@localhost/qrforge'
    )
}
```

## Rate Limiting (Production)

For production, replace `qr_site/middleware.py` with django-ratelimit + Redis:
```bash
pip install django-ratelimit django-redis
```
