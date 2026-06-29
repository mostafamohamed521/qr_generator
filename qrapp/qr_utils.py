"""
qr_utils.py
-----------
All QR-code generation logic, isolated from Django.
"""
import base64
import io
import re
from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_M
from PIL import Image, ImageDraw, ImageFont

try:
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, SquareModuleDrawer
    _HAS_STYLED = True
except ImportError:
    _HAS_STYLED = False


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_qr_object(error_correction=ERROR_CORRECT_H):
    return qrcode.QRCode(
        version=1,
        error_correction=error_correction,
        box_size=10,
        border=4,
    )


def _to_base64(pil_img):
    buf = BytesIO()
    pil_img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


# ── main generator ────────────────────────────────────────────────────────────

def generate_qr_image(data: str, size: int = 300,
                      color: str = '#000000', bg: str = '#ffffff',
                      style: str = 'square',
                      logo_b64: str = None) -> str:
    """Return a base64-encoded PNG data-URI of the QR code."""
    size = max(100, min(1000, int(size)))
    transparent_bg = isinstance(bg, str) and bg.strip().lower() == 'transparent'
    fill_bg = '#ffffff' if transparent_bg else bg

    # Use lower error correction if no logo, higher if logo (needs redundancy)
    ec = ERROR_CORRECT_H if logo_b64 else ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    try:
        if style == 'rounded' and _HAS_STYLED:
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer(),
                fill_color=color,
                back_color=fill_bg,
            )
        else:
            img = qr.make_image(fill_color=color, back_color=fill_bg)
    except Exception:
        img = qr.make_image(fill_color=color, back_color=fill_bg)

    img = img.convert('RGBA')

    if transparent_bg:
        white = (255, 255, 255)
        pixels = img.load()
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]
                if (r, g, b) == white:
                    pixels[x, y] = (r, g, b, 0)

    img = img.resize((size, size), Image.LANCZOS)

    # Embed logo if provided
    if logo_b64:
        try:
            # strip data URI prefix if present
            if ',' in logo_b64:
                logo_b64 = logo_b64.split(',', 1)[1]
            logo_data = base64.b64decode(logo_b64)
            logo = Image.open(BytesIO(logo_data)).convert('RGBA')

            logo_size = int(size * 0.22)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

            # white circle background for logo
            bg_circle = Image.new('RGBA', (logo_size + 16, logo_size + 16), (255, 255, 255, 255))
            draw = ImageDraw.Draw(bg_circle)
            draw.ellipse([0, 0, logo_size + 15, logo_size + 15], fill=(255, 255, 255, 255))

            pos_bg = ((size - logo_size - 16) // 2, (size - logo_size - 16) // 2)
            pos = ((size - logo_size) // 2, (size - logo_size) // 2)

            img.paste(bg_circle, pos_bg, bg_circle)
            img.paste(logo, pos, logo)
        except Exception:
            pass  # logo embed failed silently

    if transparent_bg:
        # Preserve alpha channel — save directly as RGBA PNG
        buf = BytesIO()
        img.save(buf, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()

    # Convert back to RGB for PNG save (opaque background)
    final = Image.new('RGB', img.size, (255, 255, 255))
    final.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)

    return _to_base64(final)


def generate_qr_svg(data: str, color: str = '#000000', bg: str = '#ffffff') -> str:
    """Return an SVG string of the QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    n = len(matrix)
    cell = 10
    total = n * cell

    rects = []
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if val:
                x = c * cell
                y = r * cell
                rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{color}"/>')

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" '
        f'width="{total}" height="{total}">'
        f'<rect width="{total}" height="{total}" fill="{bg}"/>'
        + ''.join(rects) +
        '</svg>'
    )
    return svg


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
