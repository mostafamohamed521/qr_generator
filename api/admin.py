from django.contrib import admin
from .models import APIKey, WebhookEndpoint


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    # Never expose `key` (legacy plaintext, old rows only) or `key_hash`
    # (not a secret itself, but no reason to surface it either) in the
    # admin list/detail views — key_prefix is enough to identify a key.
    list_display   = ('id', 'user', 'name', 'key_prefix', 'is_active', 'last_used_at', 'created_at')
    list_filter    = ('is_active', 'created_at')
    search_fields  = ('name', 'user__username', 'user__email', 'key_prefix')
    readonly_fields = ('key_prefix', 'created_at', 'last_used_at')
    exclude        = ('key', 'key_hash')


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    # `secret` signs every delivery to the user's own endpoint — don't
    # surface it in a list view any admin/staff account can browse.
    list_display   = ('id', 'user', 'target_url', 'event', 'is_active', 'created_at')
    list_filter    = ('event', 'is_active', 'created_at')
    search_fields  = ('user__username', 'user__email', 'target_url')
    readonly_fields = ('created_at',)
    exclude        = ('secret',)
