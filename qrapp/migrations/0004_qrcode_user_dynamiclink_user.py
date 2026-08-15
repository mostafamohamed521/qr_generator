from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('qrapp', '0003_dynamiclink_scanevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='qrcode',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='qr_codes',
                to=settings.AUTH_USER_MODEL,
                null=True,  # transitional: allows applying against a non-empty table
            ),
        ),
        migrations.AddField(
            model_name='dynamiclink',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='dynamic_links',
                to=settings.AUTH_USER_MODEL,
                null=True,  # transitional: allows applying against a non-empty table
            ),
        ),
    ]
