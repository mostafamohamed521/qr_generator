from django.contrib import admin
from .models import Profile, EmailVerificationToken, AuditLogEntry

admin.site.register(Profile)
admin.site.register(EmailVerificationToken)
admin.site.register(AuditLogEntry)
