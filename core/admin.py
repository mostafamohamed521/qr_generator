from django.contrib import admin
from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display   = ('email', 'created_at')
    search_fields  = ('email', 'message')
    readonly_fields = ('email', 'message', 'created_at')
