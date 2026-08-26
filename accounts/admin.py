from django.contrib import admin
from .models import Profile, EmailVerificationToken, AuditLogEntry


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # two_factor_secret is a live TOTP shared secret — showing it in admin
    # would let any staff account regenerate valid 2FA codes for a user,
    # defeating the point of 2FA. It's excluded from every admin view.
    list_display  = ('user', 'is_email_verified', 'two_factor_enabled', 'theme_preference', 'created_at')
    list_filter   = ('is_email_verified', 'two_factor_enabled', 'theme_preference', 'language_preference')
    search_fields = ('user__username', 'user__email')
    exclude       = ('two_factor_secret',)
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user',)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    # The raw token is a bearer credential (whoever has it can verify that
    # email) — never displayed, only whether one exists and its state.
    list_display    = ('user', 'used', 'created_at')
    list_filter     = ('used', 'created_at')
    search_fields   = ('user__username', 'user__email')
    readonly_fields = ('user', 'created_at', 'used')
    exclude         = ('token',)

    def has_add_permission(self, request):
        return False


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display    = ('created_at', 'user', 'team', 'action')
    list_filter     = ('action', 'created_at')
    search_fields   = ('user__username', 'user__email', 'action')
    readonly_fields = ('user', 'team', 'action', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False
