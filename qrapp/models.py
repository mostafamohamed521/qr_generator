from django.conf import settings
from django.db import models


class QRCode(models.Model):
    TYPE_CHOICES = [
        ('url',      'URL'),
        ('text',     'Text'),
        ('contact',  'Contact / vCard'),
        ('wifi',     'WiFi'),
        ('sms',      'SMS'),
        ('email',    'Email'),
        ('phone',    'Phone'),
        ('location', 'Location'),
    ]

    # Nullable for now so this migration is safe to run against a database that
    # already has rows (pre-ownership data has no owner). The application layer
    # never serves or lets a request touch a QRCode with user=None; once a
    # backfill/cleanup has run in your environment, this can be tightened to
    # null=False in a follow-up migration.
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='qr_codes', null=True, blank=True)
    qr_type    = models.CharField(max_length=20, choices=TYPE_CHOICES)
    label      = models.CharField(max_length=120, blank=True, default='')
    content    = models.TextField()
    qr_color   = models.CharField(max_length=20, default='#000000')
    bg_color   = models.CharField(max_length=20, default='#ffffff')
    qr_size    = models.PositiveIntegerField(default=300)
    qr_style   = models.CharField(max_length=20, default='square')
    image_b64  = models.TextField(blank=True, default='')
    scan_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'QR Code'
        verbose_name_plural = 'QR Codes'

    def display_label(self):
        if self.label:
            return self.label
        if self.content:
            return self.content[:50]
        return self.get_qr_type_display()

    def __str__(self):
        return f"[{self.get_qr_type_display()}] {self.display_label()} — {self.created_at:%Y-%m-%d %H:%M}"


import secrets
from django.utils import timezone


def _gen_code():
    """Generate a unique 8-character short code."""
    return secrets.token_urlsafe(6)[:8]


class DynamicLink(models.Model):
    """A QR code whose destination URL can be edited without reprinting."""
    # See QRCode.user for why this is nullable.
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name='dynamic_links', null=True, blank=True)
    short_code  = models.CharField(max_length=20, unique=True, default=_gen_code, db_index=True)
    label       = models.CharField(max_length=120, blank=True, default='')
    target_url  = models.URLField(max_length=2000)
    image_b64   = models.TextField(blank=True, default='')
    qr_color    = models.CharField(max_length=20, default='#000000')
    bg_color    = models.CharField(max_length=20, default='#ffffff')
    qr_style    = models.CharField(max_length=20, default='square')
    scan_count  = models.PositiveIntegerField(default=0)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Dynamic Link'
        verbose_name_plural = 'Dynamic Links'

    def display_label(self):
        return self.label or self.target_url[:50]

    def __str__(self):
        return f"[{self.short_code}] {self.display_label()}"


class ScanEvent(models.Model):
    """One scan of a DynamicLink — stored for per-link analytics."""
    link        = models.ForeignKey(DynamicLink, on_delete=models.CASCADE, related_name='scans')
    scanned_at  = models.DateTimeField(default=timezone.now, db_index=True)
    ip_hash     = models.CharField(max_length=64, blank=True, default='')
    user_agent  = models.TextField(blank=True, default='')
    referer     = models.URLField(max_length=500, blank=True, default='')

    class Meta:
        ordering = ['-scanned_at']
