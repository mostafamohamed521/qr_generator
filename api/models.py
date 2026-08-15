import hashlib
import secrets
from django.conf import settings
from django.db import models


def generate_api_key():
    return 'qrf_' + secrets.token_urlsafe(32)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class APIKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_keys')
    # Present but intentionally unused — see NOTES from the api-app audit.
    # Every APIKey created so far belongs to an individual user; nothing
    # reads or writes this field. Left as-is (documented, not removed and
    # not wired up) rather than guessing at an unrequested team-API-key
    # feature or a destructive schema change.
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE, null=True, blank=True, related_name='api_keys')
    name = models.CharField(max_length=80, default='Default key')
    # The raw key is shown to the user exactly once, at creation, in the
    # create_key response — never stored or displayed again. Only its
    # SHA-256 hash is persisted and used for authentication lookups
    # (authenticate_api_key hashes the incoming Authorization header value
    # and looks up by key_hash). key_prefix is just enough of the key
    # (its non-secret 'qrf_' + a few chars) to let a user recognize which
    # key is which in a list, the same pattern GitHub/Stripe use.
    key_hash = models.CharField(max_length=64, unique=True, db_index=True, default='')
    key_prefix = models.CharField(max_length=16, blank=True, default='')
    # Legacy plaintext column. Kept, not dropped, for keys created before
    # hashing was added — see the migration for why. New keys never set
    # this (see create_key in views.py): it stays blank/null going forward.
    key = models.CharField(max_length=120, unique=True, null=True, blank=True, default=None)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.key_prefix or (self.key or '')[:10]}…)"


class WebhookEndpoint(models.Model):
    """Sprint 9: notify external services on scan events."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='webhooks')
    target_url = models.URLField()
    event = models.CharField(max_length=40, default='qr.scanned')
    secret = models.CharField(max_length=64, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
