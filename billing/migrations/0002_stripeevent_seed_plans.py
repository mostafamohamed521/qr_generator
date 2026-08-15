from django.db import migrations, models


def seed_plans(apps, schema_editor):
    """
    Moves plan seeding out of the request path (billing/views.py used to call
    this on every page load) into a one-time, idempotent data migration.
    get_or_create means this is safe to run against a database that already
    has these rows with different (admin-edited) values — it will never
    overwrite existing data, only create the rows if they're missing.
    """
    Plan = apps.get_model('billing', 'Plan')
    Plan.objects.get_or_create(
        code='free',
        defaults=dict(
            name='Free', price_monthly=0,
            max_qr_per_month=50, max_dynamic_links=0,
            allows_team=False, allows_api=False,
        ),
    )
    Plan.objects.get_or_create(
        code='pro',
        defaults=dict(
            name='Pro', price_monthly=12,
            max_qr_per_month=0, max_dynamic_links=0,  # 0 = unlimited
            allows_team=True, allows_api=True,
        ),
    )


def noop_reverse(apps, schema_editor):
    # Deliberately not deleting Plan rows on reverse — by the time anyone
    # would roll this back, real Subscriptions likely reference them
    # (Plan.subscriptions uses on_delete=PROTECT, so a blind delete would
    # just fail loudly anyway). Nothing to do.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StripeEvent',
            fields=[
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('event_type', models.CharField(max_length=100)),
                ('received_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.RunPython(seed_plans, noop_reverse),
    ]
