from django.contrib import admin
from .models import QRCode, DynamicLink, ScanEvent


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display   = ('id', 'user', 'qr_type', 'label', 'is_favorite', 'qr_size', 'qr_style', 'created_at')
    list_filter    = ('qr_type', 'qr_style', 'is_favorite', 'created_at')
    search_fields  = ('label', 'content', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'content', 'image_b64')
    ordering       = ('-created_at',)
    autocomplete_fields = ('user',)


class ScanEventInline(admin.TabularInline):
    model = ScanEvent
    extra = 0
    readonly_fields = ('scanned_at', 'ip_hash', 'user_agent', 'referer')
    can_delete = False
    max_num = 20
    ordering = ('-scanned_at',)


@admin.register(DynamicLink)
class DynamicLinkAdmin(admin.ModelAdmin):
    list_display   = ('id', 'user', 'short_code', 'label', 'target_url', 'scan_count', 'is_active', 'created_at')
    list_filter    = ('is_active', 'qr_style', 'created_at')
    search_fields  = ('label', 'short_code', 'target_url', 'user__username', 'user__email')
    readonly_fields = ('short_code', 'created_at', 'updated_at', 'image_b64')
    ordering       = ('-created_at',)
    autocomplete_fields = ('user',)
    inlines        = [ScanEventInline]


@admin.register(ScanEvent)
class ScanEventAdmin(admin.ModelAdmin):
    list_display  = ('id', 'link', 'scanned_at', 'ip_hash')
    list_filter   = ('scanned_at',)
    readonly_fields = ('link', 'scanned_at', 'ip_hash', 'user_agent', 'referer')
    ordering      = ('-scanned_at',)
