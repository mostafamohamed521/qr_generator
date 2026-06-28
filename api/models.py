import secrets
from django.conf import settings
from django.db import models


def generate_api_key():
    return 'qrf_' + secrets.token_urlsafe(32)


class APIKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE, null=True, blank=True, related_name='api_keys')
    name = models.CharField(max_length=80, default='Default key')
    key = models.CharField(max_length=120, unique=True, default=generate_api_key)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.key[:10]}…)"


class WebhookEndpoint(models.Model):
    """Sprint 9: notify external services on scan events."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webhooks')
    target_url = models.URLField()
    event = models.CharField(max_length=40, default='qr.scanned')
    secret = models.CharField(max_length=64, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
