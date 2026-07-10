# 🔳 QR Forge

<p align="center">
  <img src="https://img.shields.io/badge/Django-4.2.7-092E20?style=for-the-badge&logo=django&logoColor=white">
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/JavaScript-ES6-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black">
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white">
  <img src="https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge">
</p>

<p align="center">
A modern, secure, and feature-rich QR Code Generator built with Django.
Create beautiful and customizable QR Codes with a clean interface, history management, and production-ready architecture.
</p>

---

# ✨ Features

- 🔗 Generate QR Codes for **8 different data types**
  - URL
  - Plain Text
  - Contact (vCard)
  - WiFi
  - SMS
  - Email
  - Phone Number
  - Google Maps Location

- 🎨 Customize QR Color
- 🖼️ Customize Background Color
- 📏 Adjustable Size (150px → 800px)
- 🔲 Multiple QR Styles (Square / Rounded)
- ⚡ Instant Preview
- 💾 Download as PNG
- 📋 Copy to Clipboard
- 📤 Native Share API
- 🏷️ QR Labels
- 🕘 History with Thumbnail Preview
- 🗑️ Delete Individual QR Codes
- 🧹 Clear History
- 👨‍💼 Django Admin Dashboard

---

# 🏗 Project Architecture

```
QR-Forge/
│
├── manage.py
├── requirements.txt
├── README.md
├── .env.example
│
├── qr_site/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── qrapp/
│   ├── admin.py
│   ├── forms.py
│   ├── models.py
│   ├── qr_utils.py
│   ├── urls.py
│   ├── views.py
│   ├── tests.py
│   └── migrations/
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   └── js/
│
├── media/
│
└── staticfiles/
```

---

# 🚀 Tech Stack

### Backend

- Python 3.14
- Django 4.2

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript (ES6)

### Database

- SQLite (Development)
- PostgreSQL Ready

### Deployment

- Gunicorn
- WhiteNoise
- Nginx
- Environment Variables (.env)

---

# 📸 Screenshots

## Home

```
screenshots/home.png
```

## QR Generator

```
screenshots/generator.png
```

## History

```
screenshots/history.png
```

---

# ⚙️ Installation

## Clone Repository

```bash
git clone https://github.com/yourusername/QR-Forge.git

cd QR-Forge
```

---

## Create Virtual Environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment

Create a `.env` file

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
```

---

## Apply Migrations

```bash
python manage.py migrate
```

---

## Create Admin

```bash
python manage.py createsuperuser
```

---

## Run Server

```bash
python manage.py runserver
```

Open

```
http://127.0.0.1:8000
```

Admin

```
http://127.0.0.1:8000/admin
```

---

# 🔌 API Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/` | Home Page |
| POST | `/api/generate/` | Generate QR |
| GET | `/api/history/` | History |
| POST | `/api/delete/<id>/` | Delete QR |
| POST | `/api/clear/` | Clear History |

---

# 🧪 Running Tests

```bash
python manage.py test qrapp -v 2
```

---

# 🔒 Security

- CSRF Protection
- Secure Cookies
- HSTS Support
- Environment Variables
- WhiteNoise Static Serving
- Rate Limiting Ready
- Secure Password Validation

---

# 📈 Future Improvements

- User Authentication
- Cloud Sync
- QR Analytics
- Logo Upload
- SVG Export
- REST API
- Docker Support
- Dark Mode
- Multi-language Support

---

# 🚀 Deployment

Production-ready using:

- Gunicorn
- WhiteNoise
- Nginx
- PostgreSQL
- Ubuntu Server

---

# 🤝 Contributing

Contributions are welcome.

Feel free to fork the project and submit a Pull Request.

---

# 📄 License

This project is licensed under the MIT License.

---

# 👨‍💻 Author

## Mostafa Mohamed

Computer Science Student

Backend Django Developer

GitHub

https://github.com/mostafamohamed521

LinkedIn

(Add your LinkedIn profile here)

---

<p align="center">

⭐ If you like this project, don't forget to give it a Star.

Made with ❤️ using Django.

</p>