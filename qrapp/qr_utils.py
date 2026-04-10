"""
qr_utils.py
-----------
All QR-code generation logic, isolated from Django.
"""
import base64
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_H

try:
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    _HAS_STYLED = True
except ImportError:
    _HAS_STYLED = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_qr_object():
    return qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )


def _to_base64(pil_img):
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


# ── main generator ────────────────────────────────────────────────────────────

def generate_qr_image(data: str, size: int = 300,
                      color: str = '#000000', bg: str = '#ffffff',
                      style: str = 'square') -> str:
    """Return a base64-encoded PNG data-URI of the QR code."""
    size = max(100, min(1000, int(size)))

    qr = _make_qr_object()
    qr.add_data(data)
    qr.make(fit=True)

    try:
        if style == 'rounded' and _HAS_STYLED:
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer(),
                fill_color=color,
                back_color=bg,
            )
        else:
            img = qr.make_image(fill_color=color, back_color=bg)
    except Exception:
        img = qr.make_image(fill_color=color, back_color=bg)

    img = img.resize((size, size))
    return _to_base64(img)


# ── content builders ──────────────────────────────────────────────────────────

def build_url(url: str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def build_vcard(d: dict) -> str:
    fn = f"{d.get('first_name','')} {d.get('last_name','')}".strip()
    return (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        f"FN:{fn}\r\n"
        f"N:{d.get('last_name','')};{d.get('first_name','')};;;\r\n"
        f"ORG:{d.get('organization','')}\r\n"
        f"TITLE:{d.get('title','')}\r\n"
        f"TEL;TYPE=WORK,VOICE:{d.get('phone','')}\r\n"
        f"TEL;TYPE=CELL:{d.get('mobile','')}\r\n"
        f"EMAIL:{d.get('email','')}\r\n"
        f"URL:{d.get('website','')}\r\n"
        f"ADR;TYPE=WORK:;;{d.get('address','')};;;;\r\n"
        "END:VCARD"
    )


def build_wifi(ssid: str, password: str, encryption: str) -> str:
    if encryption == 'nopass':
        return f"WIFI:T:nopass;S:{ssid};P:;;"
    return f"WIFI:T:{encryption};S:{ssid};P:{password};;"


def build_sms(phone: str, message: str) -> str:
    return f"SMSTO:{phone}:{message}"


def build_email(email: str, subject: str, body: str) -> str:
    return f"MATMSG:TO:{email};SUB:{subject};BODY:{body};;"


def build_phone(phone: str) -> str:
    return f"tel:{phone}"


def build_location(lat: float, lng: float) -> str:
    return f"geo:{lat},{lng}"
