"""
Time-based One-Time Password (TOTP) two-factor authentication.
Compatible with Google Authenticator, Authy, 1Password, etc.
"""
import pyotp
from qrapp.qr_utils import generate_qr_image


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str, issuer: str = 'QR Forge') -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def generate_setup_qr(secret: str, email: str) -> str:
    """Return a base64 QR code image the user scans with their authenticator app."""
    uri = provisioning_uri(secret, email)
    return generate_qr_image(uri, size=240, color='#15122b', bg='#ffffff')


def verify_code(secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code, allowing 1 step of clock drift (±30s)."""
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=1)
