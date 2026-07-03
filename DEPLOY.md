# QR Forge — Deployment Guide

## Environment Variables

```bash
DJANGO_SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

## Production Setup (Ubuntu/Debian)

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install gunicorn whitenoise

# 2. Collect static files
python manage.py collectstatic --noinput

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
