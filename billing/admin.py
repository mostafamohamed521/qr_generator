from django.contrib import admin
from .models import Plan, Subscription, StripeEvent

admin.site.register(Plan)
admin.site.register(Subscription)
admin.site.register(StripeEvent)
