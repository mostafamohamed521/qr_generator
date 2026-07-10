# 🚀 QR Forge — Production Deployment Guide

This guide explains how to deploy **QR Forge** in a production environment using **Gunicorn**, **Nginx**, **WhiteNoise**, and optionally **PostgreSQL**.

---

# Requirements

* Python 3.14+
* pip
* Git
* Ubuntu 22.04+
* Nginx
* Gunicorn
* (Optional) PostgreSQL
* (Recommended) Redis

---

# 1. Clone the Repository

```bash
git clone https://github.com/yourusername/QR-Forge.git

cd QR-Forge
```

---

# 2. Create Virtual Environment

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

---

# 3. Install Dependencies

```bash
pip install --upgrade pip

pip install -r requirements.txt
```

---

# 4. Environment Variables

Create a `.env` file.

Example:

```env
DJANGO_SECRET_KEY=your-super-secret-key

DJANGO_DEBUG=False

DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

DATABASE_URL=sqlite:///db.sqlite3
```

For PostgreSQL:

```env
DATABASE_URL=postgresql://username:password@localhost/qrforge
```

---

# 5. Apply Database Migrations

```bash
python manage.py migrate
```

---

# 6. Create Superuser

```bash
python manage.py createsuperuser
```

---

# 7. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

---

# 8. Verify Deployment Settings

```bash
python manage.py check --deploy
```

Resolve all reported warnings before going live.

---

# 9. Run with Gunicorn

```bash
gunicorn qr_site.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 60
```

---

# 10. Configure Nginx

Example:

```nginx
server {

    listen 80;

    server_name yourdomain.com;

    location /static/ {
        alias /var/www/qrforge/staticfiles/;
    }

    location /media/ {
        alias /var/www/qrforge/media/;
    }

    location / {

        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;

        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

    }

}
```

Reload:

```bash
sudo nginx -t

sudo systemctl restart nginx
```

---

# 11. HTTPS

Install SSL using Certbot.

```bash
sudo certbot --nginx
```

---

# 12. Production Security Checklist

* DEBUG=False
* Strong SECRET_KEY
* HTTPS Enabled
* HSTS Enabled
* Secure Cookies Enabled
* WhiteNoise Enabled
* Environment Variables Used
* ALLOWED_HOSTS Configured
* CSRF_TRUSTED_ORIGINS Configured
* Rate Limiting Enabled
* Logging Enabled

---

# 13. Optional Improvements

## PostgreSQL

Replace SQLite with PostgreSQL for better scalability.

---

## Redis

Use Redis for:

* Rate Limiting
* Cache
* Sessions

Recommended packages:

```bash
pip install django-redis

pip install django-ratelimit
```

---

## Docker

Containerize the application using:

* Docker
* Docker Compose

---

## CI/CD

Recommended:

* GitHub Actions
* Render Deploy Hook
* Railway
* VPS Auto Deploy

---

# Production Requirements

```text
gunicorn>=21.2

whitenoise>=6.7

python-dotenv>=1.0

dj-database-url>=3.0

psycopg2-binary>=2.9
```

---

# Deployment Targets

QR Forge can be deployed on:

* Render
* Railway
* DigitalOcean
* AWS EC2
* Azure
* Google Cloud
* Ubuntu VPS

---

# Final Verification

Run:

```bash
python manage.py check --deploy
```

Expected result:

```
System check identified no issues (0 silenced).
```

Congratulations! 🎉

Your application is now production-ready.
