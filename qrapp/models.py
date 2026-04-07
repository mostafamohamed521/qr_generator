from django.db import models

class QRHistory(models.Model):
    TYPE_CHOICES = [
        ('url', 'URL'),
        ('text', 'Text'),
        ('contact', 'Contact'),
        ('wifi', 'WiFi'),
        ('sms', 'SMS'),
        ('email', 'Email'),
    ]
    
    qr_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_qr_type_display()} - {self.created_at}"