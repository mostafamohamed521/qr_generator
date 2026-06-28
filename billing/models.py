from django.conf import settings
from django.db import models


class Plan(models.Model):
    """Free / Pro etc. Seeded via a data migration in Sprint 10."""
    code = models.SlugField(max_length=30, unique=True)   # 'free', 'pro'
    name = models.CharField(max_length=60)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_qr_per_month = models.PositiveIntegerField(default=50)
    max_dynamic_links = models.PositiveIntegerField(default=0)
    allows_team = models.BooleanField(default=False)
    allows_api = models.BooleanField(default=False)
    stripe_price_id = models.CharField(max_length=80, blank=True, default='')

    def __str__(self):
        return self.name


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'), ('trialing', 'Trialing'),
        ('past_due', 'Past due'), ('canceled', 'Canceled'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='active')
    stripe_customer_id = models.CharField(max_length=80, blank=True, default='')
    stripe_subscription_id = models.CharField(max_length=80, blank=True, default='')
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} → {self.plan.code}"
