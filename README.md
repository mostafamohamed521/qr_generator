# QR Forge 🔳

Professional QR Code Generator built with Django 4.2 + vanilla JS.

## Features
- **8 QR types**: URL, Text, Contact (vCard), WiFi, SMS, Email, Phone, Location
- **Custom colors**: QR color + background color
- **Custom size**: 150px → 800px
- **Two styles**: Square & Rounded modules
- **History**: last 40 QR codes with thumbnails, click to re-preview
- **Actions**: Save (PNG), Copy to clipboard, Share (Web Share API)
- **Labels**: name your QR codes for easy identification
- **Django Admin** panel to manage all records

## Project Structure

```
qr_forge/
├── manage.py
├── requirements.txt
├── README.md
├── db.sqlite3              ← created on first migrate
│
├── qr_site/                ← Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── qrapp/                  ← Main application
│   ├── models.py           ← QRCode model
│   ├── views.py            ← 5 API views
│   ├── forms.py            ← 8 form classes (one per QR type)
│   ├── qr_utils.py         ← All QR generation logic
│   ├── urls.py             ← App URL routing
│   ├── admin.py            ← Django admin config
│   ├── apps.py
│   ├── tests.py            ← 44 tests
│   └── migrations/
│       └── 0001_initial.py
│
├── templates/
│   └── index.html          ← Main page template
│
└── static/
    ├── css/
    │   └── style.css       ← All styles
    └── js/
        └── app.js          ← All frontend logic
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Apply migrations
python manage.py migrate

# 3. (Optional) Create admin user
python manage.py createsuperuser

# 4. Run the server
python manage.py runserver

# Open: http://127.0.0.1:8000
# Admin: http://127.0.0.1:8000/admin
```

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET  | `/` | Main page |
| POST | `/api/generate/` | Generate a QR code |
| GET  | `/api/history/` | Get last 40 QR codes |
| POST | `/api/delete/<id>/` | Delete a QR code |
| POST | `/api/clear/` | Clear all history |

## Run Tests

```bash
python manage.py test qrapp -v 2
# → 44 tests, all passing
```
