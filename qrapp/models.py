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

    qr_type    = models.CharField(max_length=20, choices=TYPE_CHOICES)
    label      = models.CharField(max_length=120, blank=True, default='')
    content    = models.TextField()
    qr_color   = models.CharField(max_length=20, default='#000000')
    bg_color   = models.CharField(max_length=20, default='#ffffff')
    qr_size    = models.PositiveIntegerField(default=300)
    qr_style   = models.CharField(max_length=20, default='square')
    image_b64  = models.TextField(blank=True, default='')   # base64 PNG stored
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'QR Code'
        verbose_name_plural = 'QR Codes'

    def display_label(self):
        """Return label, falling back to content snippet or type name."""
        if self.label:
            return self.label
        if self.content:
            return self.content[:50]
        return self.get_qr_type_display()

    def __str__(self):
        return f"[{self.get_qr_type_display()}] {self.display_label()} — {self.created_at:%Y-%m-%d %H:%M}"
