from django.contrib import admin
from .models import APIKey, WebhookEndpoint

admin.site.register(APIKey)
admin.site.register(WebhookEndpoint)
