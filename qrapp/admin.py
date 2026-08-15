from django.contrib import admin
from .models import QRCode


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display   = ('id', 'user', 'qr_type', 'label', 'qr_size', 'qr_style', 'created_at')
    list_filter    = ('qr_type', 'qr_style', 'created_at')
    search_fields  = ('label', 'content', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'content', 'image_b64')
    ordering       = ('-created_at',)
    autocomplete_fields = ('user',)
