from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('',                      views.billing_page,    name='billing'),
    path('api/current/',          views.current_plan,    name='current_plan'),
    path('api/upgrade/',          views.upgrade_plan,    name='upgrade'),
    path('api/cancel/',           views.cancel_plan,     name='cancel'),
    path('api/stripe-webhook/',   views.stripe_webhook,  name='stripe_webhook'),
]
