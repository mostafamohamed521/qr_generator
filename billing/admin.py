from django.contrib import admin
from .models import Plan, Subscription, StripeEvent


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'price_monthly', 'max_qr_per_month', 'allows_team', 'allows_api')
    search_fields = ('name', 'code')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'plan', 'status', 'current_period_end', 'created_at')
    list_filter   = ('plan', 'status')
    search_fields = ('user__username', 'user__email', 'stripe_customer_id', 'stripe_subscription_id')
    autocomplete_fields = ('user',)
    readonly_fields = ('created_at',)


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display  = ('id', 'event_type', 'received_at')
    list_filter   = ('event_type', 'received_at')
    search_fields = ('id', 'event_type')
    readonly_fields = ('id', 'event_type', 'received_at')

    def has_add_permission(self, request):
        return False
